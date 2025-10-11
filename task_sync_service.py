"""Utility helpers for triggering Anycross webhook flows."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Tuple

import requests


logger = logging.getLogger(__name__)

DEFAULT_PAYLOAD_TEMPLATE: Dict[str, Any] = {
    "操作": "同步任务",
    "任务名称": "",
    "任务备注": "",
    "执行者": [],  # 成员字段期望列表
    "任务截止时间": "",
    "任务状态": "",
    "任务关注者": [],
    "任务评论": "",
}


class AnycrossTriggerError(RuntimeError):
    """Raised when the Anycross webhook cannot be invoked successfully."""


class AnycrossInvokeTimeout(AnycrossTriggerError):
    """Special case: Anycross accepted the request but timed out before replying."""


def trigger_anycross_webhook(
    webhook_url: str,
    payload: Dict[str, Any],
    *,
    timeout: int = 15,
) -> Tuple[int, Any]:
    """POST payload to the given Anycross webhook URL and return (status, body)."""

    if not webhook_url:
        raise AnycrossTriggerError("webhook_url is required")

    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout)
    except requests.RequestException as exc:  # network or SSL failure
        raise AnycrossTriggerError(f"Network error: {exc}") from exc

    body: Any
    try:
        body = response.json()
    except ValueError:
        body = response.text

    if response.status_code >= 400:
        if isinstance(body, dict) and str(body.get("code")) == "5":
            raise AnycrossInvokeTimeout(
                f"HTTP {response.status_code}: {body}"
            )
        raise AnycrossTriggerError(
            f"HTTP {response.status_code}: {body}"
        )

    return response.status_code, body


# ---- Batch job utilities -------------------------------------------------

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _normalize_record_entry(entry: Any) -> Tuple[str | None, Dict[str, Any] | None, str | None]:
    """Return (record_id, payload, error_message)."""
    if isinstance(entry, str):
        record_id = entry.strip()
        if not record_id:
            return None, None, "recordId is empty"
        return record_id, None, None

    if isinstance(entry, dict):
        payload = entry.get("payload")
        if payload is not None and not isinstance(payload, dict):
            return None, None, "payload must be an object"

        raw_id = entry.get("recordId") or entry.get("id")
        if not raw_id and isinstance(payload, dict):
            raw_id = payload.get("任务表行")

        record_id = raw_id.strip() if isinstance(raw_id, str) else None
        if not isinstance(record_id, str) or not record_id.strip():
            return None, None, "recordId is required"
        return record_id, payload, None

    return None, None, "Invalid record entry"


def _assemble_payload(record_id: str, payload: Dict[str, Any] | None) -> Dict[str, Any]:
    final_payload: Dict[str, Any] = dict(DEFAULT_PAYLOAD_TEMPLATE)
    final_payload["任务表行"] = record_id

    if payload:
        for key, value in payload.items():
            final_payload[key] = value

    raw_id = final_payload.get("任务表行")
    if isinstance(raw_id, str):
        stripped = raw_id.strip()
        if stripped:
            final_payload["任务表行"] = stripped
        else:
            final_payload["任务表行"] = record_id
    else:
        final_payload["任务表行"] = record_id

    return final_payload


def process_single_record(
    webhook_url: str,
    record_entry: Any,
    *,
    timeout: int = 70,
) -> Dict[str, Any]:
    record_id, payload, error = _normalize_record_entry(record_entry)
    if error:
        return {"recordId": None, "status": "error", "message": error}

    final_payload = _assemble_payload(record_id, payload)

    try:
        logger.info("Triggering Anycross webhook for record %s", record_id)
        http_status, body = trigger_anycross_webhook(
            webhook_url,
            final_payload,
            timeout=timeout,
        )
        logger.info(
            "Anycross response for %s: status=%s body=%s",
            record_id,
            http_status,
            body,
        )
        return {
            "recordId": record_id,
            "status": "success",
            "http": http_status,
            "body": body,
        }
    except AnycrossInvokeTimeout as exc:
        logger.warning(
            "Anycross invoke timeout for %s: %s",
            record_id,
            exc,
        )
        return {
            "recordId": record_id,
            "status": "accepted",
            "message": "Anycross flow still running (invoke timeout)",
            "detail": str(exc),
        }
    except AnycrossTriggerError as exc:
        logger.error(
            "Anycross trigger failed for %s: %s",
            record_id,
            exc,
        )
        return {
            "recordId": record_id,
            "status": "error",
            "message": str(exc),
        }


def enqueue_batch_job(
    webhook_url: str,
    records: List[Any],
    *,
    timeout: int = 70,
) -> str:
    job_id = uuid.uuid4().hex
    job_data = {
        "status": "pending",
        "results": [],
        "createdAt": time.time(),
    }

    with _jobs_lock:
        _jobs[job_id] = job_data
    logger.info(
        "enqueue_batch_job %s: %d record(s), timeout=%s",
        job_id,
        len(records),
        timeout,
    )

    def worker():
        logger.info(
            "job %s worker started on thread %s (records=%d)",
            job_id,
            threading.current_thread().name,
            len(records),
        )
        results: List[Dict[str, Any]] = []
        success_count = 0
        accepted_count = 0
        error_count = 0
        for entry in records:
            result = process_single_record(
                webhook_url,
                entry,
                timeout=timeout,
            )
            status = result.get("status")
            if status == "success":
                success_count += 1
            elif status == "accepted":
                accepted_count += 1
            else:
                error_count += 1
            results.append(result)

            with _jobs_lock:
                job_data["results"] = list(results)
                job_data["status"] = "running"
                job_data["updatedAt"] = time.time()

        total = len(results)
        if error_count == 0 and accepted_count == 0:
            overall = "success"
        elif success_count == 0 and accepted_count == 0:
            overall = "error"
        elif success_count == total:
            overall = "success"
        elif success_count == 0 and error_count == 0:
            overall = "accepted"
        else:
            overall = "partial"

        with _jobs_lock:
            job_data.update(
                {
                    "status": overall,
                    "results": list(results),
                    "completedAt": time.time(),
                }
            )
        logger.info(
            "job %s worker finished: total=%d success=%d accepted=%d error=%d status=%s",
            job_id,
            total,
            success_count,
            accepted_count,
            error_count,
            overall,
        )

    def worker_wrapper():
        try:
            worker()
        except Exception:  # noqa: BLE001
            logger.exception("job %s worker crashed", job_id)
            with _jobs_lock:
                job_data.update(
                    {
                        "status": "error",
                        "results": [],
                        "completedAt": time.time(),
                    }
                )

    thread = threading.Thread(target=worker_wrapper, daemon=True)
    thread.start()

    return job_id


def get_job_status(job_id: str, *, pop: bool = False) -> Dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        if pop:
            _jobs.pop(job_id, None)
        return dict(job)  # shallow copy
