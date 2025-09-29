# app.py
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


logging.basicConfig(level=logging.INFO)


app = Flask(__name__)

# Enable CORS for Vite dev server origins; allow POST and the automatic OPTIONS preflight with Content-Type header
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Requested-With", "Accept"],
        "max_age": 86400,  # cache preflight for 1 day
    }
})

@app.route("/api/endpoint", methods=["POST", "OPTIONS"])
def handle_summary():
    # 为什么要检查 OPTIONS 方法？
	# 1.	跨域请求（CORS）预检
	# •	当浏览器发起跨域请求时，首先会发送一个 OPTIONS 请求，这叫做 预检请求（Preflight request）。
	# •	预检请求的目的是检查服务器是否允许跨域请求，浏览器会先发 OPTIONS 请求来询问服务器是否支持跨域操作，然后再决定是否发送真正的 POST 或 GET 请求。
	# 2.	CORS 头部检查
	# •	OPTIONS 请求通常不会携带业务数据，只是用来检查服务器是否接受跨域请求。
	# •	所以在你的 Flask 应用中，当接收到 OPTIONS 请求时，我们通常返回一个 204 No Content 响应，表示预检成功，允许跨域请求。
	# 3.	为什么处理 OPTIONS 请求？
	# •	如果不处理 OPTIONS 请求，浏览器在发起实际请求时会被拦截，显示 CORS 错误。因此，我们需要显式处理 OPTIONS 请求并返回适当的响应头，告诉浏览器接下来的 POST 请求是允许的。

    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json()  # Waits for the request to arrive from the front-end and parses it into a Python dictionary. get_json() 是 Flask 框架提供的一个方法，用来从 HTTP 请求的 请求体（body）中提取 JSON 数据，并将其转换为 Python 对象（通常是字典 dict）。
    if not data or "summaryText" not in data:
        return jsonify(status="error", message="Missing summaryText"), 400  # `jsonify` can accept either a dictionary or multiple key-value pairs as parameters.
    
    summary = data["summaryText"].strip()
    if not summary:
        return jsonify(status="error", message="Empty summaryText"), 400
    # 严格按 payload 中的布尔 True 判断是否发送至对应群
    pd_flag = (data.get("pd") is True)
    ops_flag = (data.get("ops") is True)

    pd_chat = os.getenv("PD_CHAT_ID")
    ops_chat = os.getenv("OPS_CHAT_ID")

    targets = []
    if pd_flag:
        if not pd_chat:
            return jsonify(status="error", message="缺少 PD_CHAT_ID 环境变量"), 500
        targets.append(pd_chat)
    if ops_flag:
        if not ops_chat:
            return jsonify(status="error", message="缺少 OPS_CHAT_ID 环境变量"), 500
        targets.append(ops_chat)

    if not targets:
        # 两个开关均为 False，则不发送
        return jsonify(status="success", message="未发送：pd/ops 均为 false", targets=[])

    try:
        for chat_id in targets:
            send_post_from_summary_text(summary, receive_id=chat_id, receive_id_type="chat_id")
        return jsonify(status="success", message="已发送到目标群", targets=targets)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500


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

    # 单条记录调用
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

    # 批量处理多条记录
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
