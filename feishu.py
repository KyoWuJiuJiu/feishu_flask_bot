#
# The 'response' is an object, which is an instance of the 'Response' class in the 'requests' library.
# It contains the details of the HTTP response, such as status code, response body, headers, etc.

# Common attributes and methods of the 'Response' object include:
#   response.status_code  # The HTTP status code (e.g., 200 for success, 404 for not found)
#   response.text         # The content of the response as a string (for text-based responses)
#   response.json()       # A method that parses the response body as JSON and returns a Python dictionary (if the response is in JSON format)
#   response.headers      # A dictionary of the response headers (e.g., {'Content-Type': 'application/json'})
#   response.cookies      # A dictionary of cookies set by the server
#   response.url          # The final URL after following redirects, if any

# Example of how to use some of these attributes and methods:
# print(response.status_code)  # Output: 200
# print(response.text)         # Output: The response body as a string
# print(response.json())       # Output: The response body as a Python dictionary (if JSON)
# print(response.headers)      # Output: Headers dictionary

# feishu.py
import requests
import json
import time
from dotenv import load_dotenv
import os

# Load environment variables from .env (placed in project root)
load_dotenv()

# Read credentials from environment
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
CHAT_ID = os.getenv("CHAT_ID")

# Basic validation to prevent runtime NameError/misconfig
if not APP_ID or not APP_SECRET:
    raise RuntimeError("APP_ID/APP_SECRET not found in environment. Please set them in .env.")
if not CHAT_ID:
    # CHAT_ID is required by send_message default path; can also be passed in explicitly.
    # We don't raise here to allow send_message(text, receive_id=...) usage, but warn in comments.
    pass

# _cached_token will store the tenant_access_token, and _token_expiration_time will store the token's expiration time.
# 缓存 token；只在进程启动（模块首次加载）时设为 None，不会在后端长时间运行过程中自动重置
_cached_token = None  # 缓存 token；只在进程启动（模块首次加载）时设为 None，不会在后端长时间运行过程中自动重置
_token_expiration_time = None  # 缓存过期时间（epoch 秒）；同样只在进程重启/模块重载时重新置 None

# Default HTTP timeout (seconds) for Feishu API calls
_HTTP_TIMEOUT = 10

def get_tenant_access_token():
    global _cached_token, _token_expiration_time  # 使用全局变量的规则：
    # 1) 在函数外先定义变量（如 _cached_token = None）
    # 2) 在函数内如果只是读取，可以直接用，不需要 global
    # 3) 在函数内如果要修改，必须加 global，否则会新建局部变量而不是改全局

    # Check if the cached token is still valid (not expired)
    if _cached_token and time.time() < _token_expiration_time:
        return _cached_token

    # If the token has expired or is not available, request a new one
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}

    # Send a POST request to get the tenant_access_token
    try:
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=_HTTP_TIMEOUT  # HTTP 请求超时时间（秒）；与 token 的有效期无关，只限制单次请求的等待时间
        )
    except requests.RequestException as e:
        raise Exception(f"Network error when requesting tenant_access_token: {e}")
    if resp.status_code == 200:  # HTTP 层：200 表示请求成功到达飞书服务器（网络/协议成功）
        data = resp.json()
        # 业务层：飞书返回的 JSON 里 code == 0 才表示业务逻辑成功（消息发送成功、token 获取成功等）
        # Feishu API returns a response with a 'code' field to indicate whether the request was successful.
        # - If 'code' is 0, the request is successful, and the 'tenant_access_token' is returned.
        # - If 'code' is not 0, the API has encountered an error, and the 'msg' field provides details about the error.
        # The error handling logic in the backend checks the 'code' and raises an exception with the 'msg' if the code indicates failure.
        if data["code"] == 0:
            _cached_token = data["tenant_access_token"]
            # Set the expiration time (current time + expiration duration)
            _token_expiration_time = time.time() + data["expire"] #            _token_expiration_time = time.time() + data["expire"]  # 当前时间戳（秒）+ 过期时长（秒）；两者单位都是秒
            return _cached_token
        else:
            # If the API's 'code' is not 0, it means there was an error, and the error message is in 'msg'.
            raise Exception(f"Token error: {data['msg']}") # 这里没有 return，因为 raise 会中断函数执行并抛出异常，不会再继续往下执行
    raise Exception("Failed to get tenant_access_token")

def send_message(text, receive_id: str | None = None, receive_id_type: str = "chat_id"):  # receive_id: 消息接收方ID（可选，str 或 None）；若为 None，则默认使用环境变量中的 CHAT_ID
    # 类型标注 str | None → 表示 receive_id 可以是一个字符串（正常 ID），也可以是 None（默认值）。
    # = None → 如果调用时不传这个参数，就会用默认值 None。

    token = get_tenant_access_token()
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 复用统一的收件人校验逻辑
    target_id = _ensure_target_id(receive_id)

    payload = {
        "receive_id": target_id,          # The recipient ID; could be chat_id or user_id per receive_id_type
        "msg_type": "text",              # Message type
        "content": json.dumps({"text": text}) #dumps（dump string）→ 把 Python 对象 转成 JSON 字符串。
    }

    # URL query parameters specify how to interpret receive_id
    params = {
        "receive_id_type": receive_id_type,  # e.g., "chat_id" | "open_id" | "user_id"
    }
    
    # `params` will automatically be converted into a query string and appended to the URL.
    # For example, if the URL is 'https://example.com' and `params = {'key': 'value'}`,
    # the final URL will be 'https://example.com?key=value'.
    try:
        resp = requests.post(
            url,
            headers=headers,
            params=params,
            json=payload,
            timeout=_HTTP_TIMEOUT  # HTTP 请求超时时间（秒）；与 token 的有效期无关，只限制单次请求的等待时间
        )
    except requests.RequestException as e:
        raise Exception(f"Network error when sending message: {e}")
    
    # Check the response status and process the result
    if resp.status_code == 200:
        data = resp.json()
        if data["code"] == 0:
            return True
        else:
            raise Exception(f"Send error: {data['msg']}")
    else:
        raise Exception(f"HTTP error: {resp.status_code} - {resp.text}")
    

# ======================= Rich Text (post) helpers =======================

def _ensure_target_id(receive_id: str | None) -> str:
    target_id = receive_id or CHAT_ID
    if not target_id:
        raise ValueError("receive_id is required (set CHAT_ID in .env or pass receive_id explicitly)")
    return target_id

# “_”开头的函数指的是约定成俗的模块内部调用的辅助函数
def _feishu_post(url: str, headers: dict, params: dict, payload: dict):
    try:
        resp = requests.post(url, headers=headers, params=params, json=payload, timeout=_HTTP_TIMEOUT)
#    1.	requests.RequestException
# 	•	这是 Python requests 库 抛出的异常。
# 	•	发生在 请求都没成功发出或没收到任何响应 的情况：
# 	•	DNS 解析失败
# 	•	网络断开
# 	•	连接超时
# 	•	服务器完全无响应
# 👉 这类错误根本没到 HTTP 层，连 resp 对象都没有。
    except requests.RequestException as e:
        raise Exception(f"Network error when sending post: {e}")
    # 	2.	resp.status_code != 200
	# •	这是 HTTP 层的状态码检查。
	# •	说明请求已经成功发出并且收到了服务器的响应，但服务器返回了一个错误的 HTTP 状态：
	# •	401 → Unauthorized（没权限）
	# •	404 → Not Found（URL 不存在）
	# •	500 → Internal Server Error（服务器内部错误）
    if resp.status_code != 200:
        raise Exception(f"HTTP error: {resp.status_code} - {resp.text}")
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Feishu API error: {data.get('msg')} (code={data.get('code')})")
    return True


def send_post_zh_cn(zh_cn: dict, *, receive_id: str | None = None, receive_id_type: str = "chat_id") -> bool:  # 星号 * 表示后面的参数必须用关键字传递，不能作为位置参数
    """
    发送富文本 post（与调试台可用的形态一致）：content = {"zh_cn": {...}} 的 JSON 字符串。
    zh_cn 结构示例：
        {
          "title": "任务汇总",
          "content": [
            [ {"tag":"text","text":"今日任务:","style":["bold"]} ],
            [ {"tag":"text","text":"☐  1. 示例"} ]
          ]
        }
    """
    token = get_tenant_access_token()
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    params = {"receive_id_type": receive_id_type}
    target_id = _ensure_target_id(receive_id)

    payload = {
        "receive_id": target_id,
        "msg_type": "post",
        # 关键点：content 必须是“字符串化 JSON”，且外层为 {"zh_cn": {...}}
        "content": json.dumps({"zh_cn": zh_cn}, ensure_ascii=False)
    }
    return _feishu_post(url, headers, params, payload)


def _make_task_line(user_id: str, text: str) -> list[dict]:
    """一行任务：☐ + @user + 文本（斜体+加粗）。user_id 必须是可 @ 的 id。"""
    line = [
        {"tag": "text", "text": "☐   ", "style": ["italic"]},
        {"tag": "at", "user_id": user_id},
        {"tag": "text", "text": (" " + text) if text else "", "style": ["italic", "bold"]},
    ]
    return line


def build_post_zh_cn_from_sections(*, title: str, date_label: str, today_items: list[dict], week_items: list[dict]) -> dict:
    """
    根据两块内容拼装 zh_cn：
    - date_label 任务：today_items = [{"user_id": "ou_xxx", "text": "项目 - 任务 - 状态"}, ...]
    - 本周任务：week_items 同上（为空则不渲染本周标题）
    返回 zh_cn dict，可直接传给 send_post_zh_cn。
    """
    content_blocks: list[list[dict]] = []
    # 第一块：日期/今日任务标题
    content_blocks.append([{ "tag": "text", "text": f"{date_label}任务:", "style": ["bold"] }])
    if today_items:
        for item in today_items:
            uid = (item or {}).get("user_id")
            txt = (item or {}).get("text", "")
            if uid:
                content_blocks.append(_make_task_line(uid, txt))
    # 第二块：本周任务（若有）
    if week_items:
        content_blocks.append([{ "tag": "text", "text": "本周任务:", "style": ["bold"] }])
        for item in week_items:
            uid = (item or {}).get("user_id")
            txt = (item or {}).get("text", "")
            if uid:
                content_blocks.append(_make_task_line(uid, txt))

    return {"title": title, "content": content_blocks}


def send_post_from_summary_text(summary_text: str, *, title: str = "任务汇总", receive_id: str | None = None, receive_id_type: str = "chat_id") -> bool:
    """
    从前端传来的 generatedSummaryText 解析并发送富文本：
    - 支持两块：`今日任务:` / `yyyy/MM/dd任务:` 与 `本周任务:`
    - 每行任务形如：`(第1条) @ou_xxx, 项目名称, 任务名称, 状态` 或 `@ou_xxx, 项目, 任务, 状态`
    - 取第一段视为 user_id（可带前缀 '@'），其余逗号拼为文本
    """
    def parse_sections(text: str):
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        date_label = "今日"
        today_lines, week_lines = [], []
        current = None
        for ln in lines:
            if ln.endswith("任务:"):
                if ln.startswith("本周"):
                    current = "week"
                else:
                    date_label = ln[:-3]  # 去掉末尾“任务:”
                    current = "today"
                continue
            if current == "today":
                today_lines.append(ln)
            elif current == "week":
                week_lines.append(ln)
        return date_label, today_lines, week_lines

    def parse_task_line(ln: str):
        # 去掉前缀“(第N条)”
        if ln.startswith("(") and ")" in ln:
            ln = ln.split(")", 1)[1].strip()  # split(")", 1)：第二个参数表示最多分割 1 次，返回 2 个部分，这里取 [1] 即右括号后的内容
        parts = [p.strip() for p in ln.replace("，", ",").split(",") if p.strip()]
        user_id = ""
        rest = ""
        if parts:
            first = parts[0]
            user_id = first[1:] if first.startswith("@") else first
            rest = ", ".join(parts[1:]) if len(parts) > 1 else ""
        return user_id, rest

    date_label, today_raw, week_raw = parse_sections(summary_text)
    today_items = []
    for ln in today_raw:
        uid, txt = parse_task_line(ln)
        if uid:
            today_items.append({"user_id": uid, "text": txt})
    week_items = []
    for ln in week_raw:
        uid, txt = parse_task_line(ln)
        if uid:
            week_items.append({"user_id": uid, "text": txt})

    zh_cn = build_post_zh_cn_from_sections(title=title, date_label=date_label, today_items=today_items, week_items=week_items)
    return send_post_zh_cn(zh_cn, receive_id=receive_id, receive_id_type=receive_id_type)

# ===================== End Rich Text (post) helpers =====================

if __name__ == "__main__":
    # 获取 token 并进行打印
    token = get_tenant_access_token()   
    print("✅ 获取 token 成功：", token)
    
    # 测试消息
    test_msg = "🚀 飞书机器人测试成功！这是来自 Flask 项目的消息。"
    
    # 发送消息并打印结果
    result = send_message(test_msg)
    print("✅ 消息发送结果：", result)