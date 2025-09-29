# Feishu Flask Bot

A small Flask service that receives summary payloads from a front-end and forwards them to Feishu group chats as rich text posts. It wraps Feishu tenant token management, message formatting, and per-audience routing behind a single REST endpoint.

## Prerequisites
- Python 3.10+
- Feishu developer app with permissions to send group messages
- Chat IDs for the target Feishu groups (PD / OPS or any chat you plan to notify)

## Getting Started
1. Clone the repository and create a virtual environment (optional but recommended).
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
2. Create a `.env` file in the project root with your Feishu credentials. **Do not commit secrets.**
   ```env
   APP_ID=cli_xxxxxxxxxxxxxxxx
   APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   CHAT_ID=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # optional default group
   PD_CHAT_ID=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # used when request payload sets "pd": true
   OPS_CHAT_ID=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxx  # used when request payload sets "ops": true
   ```
3. Run the Flask app.
   ```bash
   python app.py
   ```
   The server listens on `http://localhost:8000` by default.

## API Reference
### `POST /api/endpoint`
- **Purpose**: Accepts a plain-text summary and delivers it to Feishu chats as a rich-text `post` message.
- **Request body**
  ```json
  {
    "summaryText": "今日任务:\n(第1条) @ou_xxx, 项目名称, 任务名称, 状态\n本周任务:\n@ou_yyy, 项目, 任务, 状态",
    "pd": true,
    "ops": false
  }
  ```
  - `summaryText` (required): Text containing two sections labeled `…任务:`. The service parses each line, extracts user IDs (with or without `@`), and formats them into Feishu checkbox lines.
  - `pd` / `ops` (optional booleans): Toggle whether to push the message to the PD / OPS chat IDs. You can add more branches by editing `app.py`.
- **Success response**
  ```json
  {
    "status": "success",
    "message": "已发送到目标群",
    "targets": ["oc_xxx", "oc_yyy"]
  }
  ```
- **Error responses**: Standardized JSON with `status="error"` and a descriptive `message` (e.g., missing env vars, empty summary, Feishu API failure).

## Feishu Integration
- `feishu.py` centralizes token fetching (`tenant_access_token`) with simple in-process caching, plus helpers for sending plain text and rich-text posts.
- The message payload is serialized to the `post` schema required by Feishu (`content` must be a JSON string).
- `curl.md` documents manual API calls if you need to debug without the Flask layer.

## Project Structure
```
app.py              # Flask entry point exposing /api/endpoint
feishu.py           # Feishu SDK helpers: token cache, rich-text builders, senders
get_token.py        # Standalone script to fetch a tenant token for debugging
curl.md             # Step-by-step curl examples
requirements.txt    # Python dependencies
```
Additional utilities (`test.py`, `test_post.py`) provide quick manual experiments for message formatting.

## Development Notes
- CORS is enabled for Vite dev servers on `localhost:5173` and `127.0.0.1:5173`. Update origins in `app.py` if your front-end runs elsewhere.
- When adding new audiences beyond PD/OPS, extend the boolean flag handling in `app.py` and populate matching chat IDs in the environment.
- The Feishu HTTP timeout defaults to 10 seconds; adjust `_HTTP_TIMEOUT` in `feishu.py` if your network requires longer waits.

## Testing
- Manually POST to the endpoint while the server is running:
  ```bash
  curl -X POST http://localhost:8000/api/endpoint \
    -H 'Content-Type: application/json' \
    -d '{"summaryText":"今日任务:\\n@ou_demo, 项目, 任务, 状态","pd":true}'
  ```
- Check Feishu group chats to confirm the message layout. For lower-level diagnostics, run the scripts in `curl.md` or `test.py` with disposable tokens.

## Troubleshooting
- **401 or auth errors**: Ensure `APP_ID` and `APP_SECRET` are valid and that you are using a fresh tenant access token.
- **"缺少 PD_CHAT_ID 环境变量"**: Set the corresponding chat ID or disable the flag in the request body.
- **No message delivered**: The service silently succeeds when both `pd` and `ops` are `false`; verify your front-end toggles.

## License
Specify your project license here (e.g., MIT, Apache-2.0) if you plan to share the code. Update this section accordingly.
