"""Ad-hoc helper for testing the `/api/task-sync` endpoint locally.

Usage (inside project root, venv activated):
    python python_doc/feishu_flask_bot/sync_task_test.py

You can adjust WEBHOOK_URL and RECORDS below to match your environment.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable

import requests


API_BASE = os.environ.get("TASK_SYNC_API", "http://localhost:8000")
SINGLE_ENDPOINT = f"{API_BASE}/api/task-sync"
STATUS_ENDPOINT = f"{API_BASE}/api/task-sync/status"

# TODO: replace with你自己的 webhook URL / record 数据
WEBHOOK_URL = "https://open.feishu.cn/anycross/trigger/callback/MTFhYTI3YmQ5ZDU0MzJmOWRhMThkNzFlMWEwNjE5YzQw"

BASE_PAYLOAD_TEMPLATE: Dict[str, Any] = {
    # 和多维表格自动化保持一致的字段骨架
    "操作": "同步任务",
    "任务名称": "",
    "任务备注": "",
    "执行者": [],
    "任务截止时间": "",
    "任务状态": "",
    "任务关注者": [],
    "任务评论": "",
}


def make_record(record_id: str, extra_fields: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(BASE_PAYLOAD_TEMPLATE)
    if extra_fields:
        payload.update(extra_fields)
    payload["任务表行"] = record_id
    return {"recordId": record_id, "payload": payload}


# 根据实际字段替换下面示例值；列表类型要传数组
RECORDS: Iterable[Any] = [
    make_record(
        "recuXOHIjy2snK"
        # {
        #     "任务名称": "示例任务A",
        #     "执行者": [  # 成员字段：数组里放 {id,type}
        #         {"id": "ou_example_user", "type": "open_id"}
        #     ],
        #     "任务截止时间": "2025/09/26 00:00",
        #     "任务状态": "opt_status_id",  # 单选下拉用 option_id
        #     "任务备注": "脚本调试",
        #     "任务关注者": [
        #         {"id": "ou_example_follower", "type": "open_id"}
        #     ],
        # },
    )
]


def call_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(SINGLE_ENDPOINT, json=payload, timeout=5)
    resp.raise_for_status()
    return resp.json()


def poll_status(job_id: str, attempts: int = 6, interval: int = 10) -> None:
    """Poll job status endpoint a few times with delay."""

    for i in range(1, attempts + 1):
        time.sleep(interval)
        try:
            resp = requests.get(f"{STATUS_ENDPOINT}/{job_id}", timeout=5)
            if resp.status_code == 404:
                print(f"[{i}] Job {job_id} not found (may have been cleaned up)")
                return
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"[{i}] Poll failed: {exc}")
            continue

        data = resp.json()
        print(f"[{i}] Status response:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        status = data.get("status")
        if status in {"success", "error", "partial", "accepted"}:
            print(f"Job {job_id} finished with status {status}")
            return

    print(f"Job {job_id} still running after {attempts * interval} seconds")


def _collect_records() -> list[Any]:
    if isinstance(RECORDS, (list, tuple, set)):
        items = list(RECORDS)
    elif not RECORDS:
        items = []
    else:
        items = [RECORDS]

    cleaned: list[Any] = []
    for item in items:
        if not item:
            continue
        cleaned.append(item)

    if not cleaned:
        raise SystemExit("No record data provided")
    return cleaned


def main() -> None:
    if not WEBHOOK_URL:
        raise SystemExit("Please set WEBHOOK_URL before running this script")

    records = _collect_records()
    print(f"Sending {len(records)} record(s) via batch endpoint...")
    payload = {"webhookUrl": WEBHOOK_URL, "records": records}
    result = call_api(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    job_id = result.get("jobId")
    if job_id:
        print(f"Will poll job status for {job_id}...")
        poll_status(job_id)


if __name__ == "__main__":
    main()
