from dotenv import load_dotenv
import requests
import os
import time

load_dotenv()

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")

_HTTP_TIMEOUT = 10

if not APP_ID or not APP_SECRET:
    raise RuntimeError("环境里面没有APP_ID和APP_SECRET变量, 请找到.env文件去添加变量")

_cached_token = None

_token_expiration_time = None

def get_tenant_access_token(app_id: str = APP_ID, app_secret: str = APP_SECRET):
    global _cached_token, _token_expiration_time

    if _cached_token and time.time() < _token_expiration_time:
        return _cached_token
    

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    payload = {"app_id": app_id, "app_secret": app_secret}

    try:
        response = requests.post(
            url=url,
            headers=headers,
            json=payload,
            timeout=_HTTP_TIMEOUT
        )
    except requests.RequestException as e:
        raise Exception(f'在获取凭证的时候网络有问题, 连接不上')
    
    if response.status_code == 200:
        data = response.json()

        if data["code"] == 0:
            _cached_token = data["tenant_access_token"]
            _token_expiration_time = time.time()+data["expire"]-10 # 为了安全把有效期缩短了10秒, 这样可以早点判断

            return _cached_token
        else:
            raise Exception(f'网络连上了, 但是服务器服务器有问题: {data["msg"]}')
    else:
        raise Exception(f'找不到凭证: {response.status_code}')
