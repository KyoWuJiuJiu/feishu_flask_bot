# curl 使用说明（直连飞书 API 发群消息）

> 说明：本文件演示如何 **直接调用飞书开放平台 API**：先获取 `tenant_access_token`，再调用 **发送消息到群** 的接口。注意保护密钥，不要把 `app_secret` 泄露到公共环境。

---

## 0. 获取 tenant_access_token

**接口**：`POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal`

```bash
# 请先把 YOUR_APP_ID / YOUR_APP_SECRET 替换为你自己的
curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "app_id": "YOUR_APP_ID",
    "app_secret": "YOUR_APP_SECRET"
  }'
```

**可选：一行命令把 token 存到变量（依赖 jq）**

```bash
TOKEN=$(curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"app_id":"YOUR_APP_ID","app_secret":"YOUR_APP_SECRET"}' | jq -r '.tenant_access_token')
```

> 若未安装 `jq`，也可以从上一步响应中手动复制 `tenant_access_token` 并赋值给 `TOKEN`。

---

## 1. 发送 **文本** 到群

**接口**：`POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id`

```bash
# 请将 oc_xxx 替换为你的群 chat_id；必须带 Authorization 头
curl -s -X POST 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "receive_id": "oc_xxxxxxxxxxxxx",
    "msg_type": "text",
    "content": "{\"text\":\"这是一条测试消息\"}"
  }'
```

> 注意：`content` **必须是字符串**，里面再放 JSON，因此要进行转义（上例中的 `\"`）。

---

## 2. 发送 **富文本 post**（每行一个段落）

```bash
curl -s -X POST 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "receive_id": "oc_xxxxxxxxxxxxx",
    "msg_type": "post",
    "content": "{\"post\":{\"zh_cn\":{\"title\":\"任务汇总\",\"content\":[[{\"tag\":\"text\",\"text\":\"今日任务:\"}],[{\"tag\":\"text\",\"text\":\"(第1条) @执行者，项目名称，任务名称，状态\"}],[{\"tag\":\"text\",\"text\":\"(第2条) ……\"}]]}}}"
  }'
```

> 结构要点：`post.zh_cn.content` 是 **二维数组**，每个内层数组是一段（可包含多个内联元素，这里只放了一个 `text`）。

---

## 3. 发送 **交互卡片 interactive**（示例）

```bash
curl -s -X POST 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{
    "receive_id": "oc_xxxxxxxxxxxxx",
    "msg_type": "interactive",
    "content": "{\"card\":{\"config\":{\"wide_screen_mode\":true},\"header\":{\"title\":{\"tag\":\"plain_text\",\"content\":\"任务汇总\"}},\"elements\":[{\"tag\":\"div\",\"text\":{\"tag\":\"lark_md\",\"content\":\"**今日任务**\\n- (1) 任务A\\n- (2) 任务B\"}}]}}"
  }'
```

---

## 4. 使用 Python + requests 调用飞书 API（替代 curl）

```python
import json
import requests

APP_ID = "YOUR_APP_ID"
APP_SECRET = "YOUR_APP_SECRET"
CHAT_ID = "oc_xxxxxxxxxxxxx"  # 群 chat_id

# 1) 获取 tenant_access_token
resp = requests.post(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    headers={"Content-Type": "application/json"},
    json={"app_id": APP_ID, "app_secret": APP_SECRET},
    timeout=10,
)
resp.raise_for_status()
data = resp.json()
if data.get("code") != 0:
    raise RuntimeError(f"get token error: {data}")
TOKEN = data["tenant_access_token"]

# 2) 发送富文本 post（示例）
url = "https://open.feishu.cn/open-apis/im/v1/messages"
params = {"receive_id_type": "chat_id"}
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

post_content = {
    "post": {
        "zh_cn": {
            "title": "任务汇总",
            "content": [
                [{"tag": "text", "text": "今日任务:"}],
                [{"tag": "text", "text": "(第1条) @执行者，项目名称，任务名称，状态"}],
            ],
        }
    }
}

payload = {
    "receive_id": CHAT_ID,
    "msg_type": "post",
    # 注意：content 要是字符串（JSON 序列化）
    "content": json.dumps(post_content, ensure_ascii=False),
}

resp2 = requests.post(url, params=params, headers=headers, json=payload, timeout=10)
resp2.raise_for_status()
print(resp2.status_code, resp2.json())
```

---

### 常见问题

- **content 为何要二次 JSON？** 飞书接口定义 `content` 为字符串，内部再是一段 JSON；所以必须 `json.dumps(...)` 或在 curl 中手动加转义。
- **鉴权失败**：token 过期或 `app_id/app_secret` 错；请重新获取 `tenant_access_token`。
- **发送给个人**：把 `receive_id_type` 改为 `open_id/user_id`，并使用对应的 `receive_id`。

> 文件名大小写：`Curl.md` 能用，但社区通常用小写 `curl.md`。可按团队规范调整。
