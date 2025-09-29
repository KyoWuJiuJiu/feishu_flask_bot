from pathlib import Path
from logging import getLogger
from logging.handlers import RotatingFileHandler
import logging
import os
from typing import Any

from flask import Flask, request, jsonify
from flask_cors import CORS

from feishu import send_post_from_summary_text
from task_sync_service import (
    AnycrossInvokeTimeout,
    AnycrossTriggerError,
    enqueue_batch_job,
    get_job_status,
    process_single_record,
)

def configure_logging() -> None:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    file_handler = RotatingFileHandler(log_file, maxBytes=1_048_576, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = getLogger()
    root.setLevel(logging.INFO)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    root.addHandler(console_handler)
    root.addHandler(file_handler)


configure_logging()

app = Flask(__name__)

# Enable CORS for Vite dev server origins; allow POST and the automatic OPTIONS preflight with Content-Type header
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Requested-With", "Accept"],
        "max_age": 86400,
    }
})


@app.route("/api/endpoint", methods=["POST", "OPTIONS"])
def handle_summary():
    # Respond to OPTIONS preflight so browsers can make the real request.
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    if "summaryText" not in data:
        return jsonify(status="error", message="Missing summaryText"), 400

    summary = data["summaryText"].strip()
    if not summary:
        return jsonify(status="error", message="Empty summaryText"), 400

    pd_flag = data.get("pd") is True
    ops_flag = data.get("ops") is True

    pd_chat = os.getenv("PD_CHAT_ID")
    ops_chat = os.getenv("OPS_CHAT_ID")

    targets = []
    if pd_flag:
        if not pd_chat:
            return jsonify(status="error", message="Missing PD_CHAT_ID environment variable"), 500
        targets.append(pd_chat)
    if ops_flag:
        if not ops_chat:
            return jsonify(status="error", message="Missing OPS_CHAT_ID environment variable"), 500
        targets.append(ops_chat)

    if not targets:
        # Both toggles disabled -> nothing to send.
        return jsonify(status="success", message="Not sent: pd/ops flags are false", targets=[])

    try:
        for chat_id in targets:
            send_post_from_summary_text(summary, receive_id=chat_id, receive_id_type="chat_id")
        return jsonify(status="success", message="Sent to targets", targets=targets)
    except Exception as exc:
        return jsonify(status="error", message=str(exc)), 500


@app.route("/api/task-sync", methods=["POST", "OPTIONS"])
def trigger_task_sync():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    webhook_url = data.get("webhookUrl")
    payload = data.get("payload")
    record_id = data.get("recordId")
    records = data.get("records")

    if not isinstance(webhook_url, str) or not webhook_url.strip():
        return jsonify(status="error", message="webhookUrl is required"), 400

    if payload is not None and not isinstance(payload, dict):
        return jsonify(status="error", message="payload must be an object"), 400

    timeout_value = data.get("timeout", 70)

    # Handle a single record call.
    if records is None:
        if payload is None:
            if not isinstance(record_id, str) or not record_id.strip():
                return jsonify(status="error", message="recordId is required"), 400
            entry: Any = record_id
        else:
            entry = {"recordId": record_id, "payload": payload}

        result = process_single_record(
            webhook_url,
            entry,
            timeout=timeout_value,
        )
        status = result.get("status")
        if status == "success":
            return jsonify(result)
        if status == "accepted":
            return jsonify(result), 202
        return jsonify(result), 502

    # Batch process multiple records.
    if not isinstance(records, list) or not records:
        return jsonify(status="error", message="records must be a non-empty list"), 400

    job_id = enqueue_batch_job(
        webhook_url,
        records,
        timeout=timeout_value,
    )
    return jsonify(status="accepted", jobId=job_id), 202


@app.route("/api/task-sync/status/<job_id>", methods=["GET"])
def get_task_sync_job(job_id: str):
    job = get_job_status(job_id, pop=False)
    if not job:
        return jsonify(status="error", message="job not found"), 404
    response = {"status": job.get("status"), "results": job.get("results", [])}
    if "createdAt" in job:
        response["createdAt"] = job["createdAt"]
    if "updatedAt" in job:
        response["updatedAt"] = job["updatedAt"]
    if "completedAt" in job:
        response["completedAt"] = job["completedAt"]
    if job.get("status") in {"success", "error", "partial", "accepted"}:
        # remove completed job from cache on final states
        get_job_status(job_id, pop=True)
    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
