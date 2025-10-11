# Feishu Flask Bot

A small Flask service that receives front‑end requests and either:
- Sends rich‑text messages to Feishu group chats, or
- Triggers an Anycross (集成流) webhook to sync tasks.

The service runs behind Nginx with HTTPS. Slow upstream webhook responses are treated as accepted (非阻塞语义)：API 立即返回 202，前端用 jobId 轮询状态。

## Prerequisites

- Python 3.10+
- Feishu developer app with group messaging permission
- Target Feishu chat IDs (PD / OPS)
- Windows + Nginx (HTTPS 9876) with a certificate whose SAN includes the IP 192.168.0.96

## Setup

1) Install dependencies
```
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Configure environment (`.env` in project root)
```
APP_ID=cli_xxxxxxxxxxxxxxxx
APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHAT_ID=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # optional
PD_CHAT_ID=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx # used when body.pd = true
OPS_CHAT_ID=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxx # used when body.ops = true
```

3) Run backend (Waitress)
```
.\venv\Scripts\python.exe serve.py
```
- Binds to `http://127.0.0.1:9876` (loopback)
- Exposed externally by Nginx: `https://192.168.0.96:9876`

## Nginx + HTTPS

- External listener: `listen 192.168.0.96:9876 ssl;`
- Upstream proxy: `proxy_pass http://127.0.0.1:9876;`
- Health endpoint (recommended):
```
location /healthz { access_log off; default_type application/json; return 200 '{"status":"ok"}'; }
```
- Certificate must include SAN iPAddress=192.168.0.96. For self‑signed/internal CA, client machines must import the root cert to trust it.

## API Reference

### POST `/api/endpoint`
- Purpose: Accept a summary text and send Feishu rich‑text posts to PD/OPS.
- Body
```
{ "summaryText": "今日任务:\n@ou_xxx, 项目, 任务, 状态", "pd": true, "ops": false }
```
- Success
```
{ "status": "success", "targets": ["oc_xxx", "oc_yyy"] }
```

### POST `/api/task-sync`
- Purpose: Trigger Anycross webhook to sync tasks.
- Single record
```
{ "webhookUrl": "https://open.feishu.cn/anycross/trigger/callback/xxx", "recordId": "ROW-001", "timeout": 15 }
```
- Batch (recommended even for 1 record)
```
{ "webhookUrl": "https://open.feishu.cn/anycross/trigger/callback/xxx", "records": ["ROW-001"], "timeout": 15 }
```
- Behavior
  - Batch: returns `202` with `jobId` immediately; poll status API for result.
  - Single: waits up to `timeout` seconds; if upstream read‑timeout occurs, treated as accepted and you can poll status later.

### GET `/api/task-sync/status/<jobId>`
- Returns `{ status, results, createdAt/updatedAt/completedAt }`, where `status` ∈ {`success`,`error`,`partial`,`accepted`}.

## Testing (Windows PowerShell)

- Message endpoint
```
C:\Windows\System32\curl.exe -i https://192.168.0.96:9876/api/endpoint ^
  -H "Content-Type: application/json" ^
  --data-raw '{ "summaryText": "今日任务:\n@ou_demo, 项目, 任务, 状态", "pd": true, "ops": false }'
```

- Task sync (batch → 202 → poll)
```
$payload = @{ webhookUrl = 'https://open.feishu.cn/anycross/trigger/callback/xxxx'; records = @('ROW-001'); timeout = 15 } | ConvertTo-Json -Compress
$resp = Invoke-RestMethod https://192.168.0.96:9876/api/task-sync -Method Post -Body $payload -ContentType 'application/json'
do { $s = Invoke-RestMethod "https://192.168.0.96:9876/api/task-sync/status/$($resp.jobId)"; $s | ConvertTo-Json -Depth 6; Start-Sleep 2 } while ($s.status -notin @('success','error','partial','accepted'))
```

## Behavior & Env Switches

- Feishu HTTP timeout: `_HTTP_TIMEOUT` in `feishu.py` (default 10s).
- Anycross read‑timeout is treated as `accepted` (async). Front‑end should poll status with `jobId`.
- SSL troubleshooting (optional):
  - `ANYCROSS_VERIFY_SSL=false` (dev only) → disable verification.
  - `ANYCROSS_CA_BUNDLE=C:\path\to\corp-root-ca.pem` → custom CA bundle for strict verification.

## Project Structure
```
app.py               # Flask app (endpoints)
feishu.py            # Feishu helpers
serve.py             # Waitress entry (127.0.0.1:9876, threads=16)
requirements.txt     # Dependencies
scripts/start_bot.ps1
scripts/start_nginx.ps1
```

## Auto Start on Boot (Windows)

Scripts provided and scheduled tasks registered:
- `FeishuFlaskBot`: runs `scripts/start_bot.ps1`
- `NginxStart`: runs `scripts/start_nginx.ps1`

Manage tasks
```
schtasks /Run /TN FeishuFlaskBot
schtasks /Run /TN NginxStart
schtasks /Query /TN FeishuFlaskBot /V /FO LIST
schtasks /Delete /TN FeishuFlaskBot /F
```

## Troubleshooting

- 401/auth: verify `APP_ID` / `APP_SECRET`.
- Missing chat IDs: set `PD_CHAT_ID` / `OPS_CHAT_ID` or disable flags in body.
- Task‑sync slow/504: use batch (202 + poll). Only when you must wait synchronously, increase request `timeout` and optionally Nginx `proxy_read_timeout`.
- Logs: app `logs/app.log`; Nginx `C:\nginx\logs\access.log`, `error.log`.

## Runtime Endpoints (current env)
- Send message: `https://192.168.0.96:9876/api/endpoint`
- Trigger sync: `https://192.168.0.96:9876/api/task-sync`
- Query status: `https://192.168.0.96:9876/api/task-sync/status/<job_id>`
