from dotenv import load_dotenv
import requests
import json
import os
import logging

from get_token import get_tenant_access_token

load_dotenv()

CHAT_ID = os.getenv("CHAT_ID")

_HTTP_TIME_OUT = 10

def createPost_zh_cn_Dic(*,summaryText: str, title: str = "近期任务发布"):
    # 先把summaryText解析成list的格式, 会分成三块,一个是datelabel(“xxxx/xx/xx任务”, 因为“本周任务”是固定的), 第二个是xxxx/xx/xx任务下面的任务组成的文本的list, 第三个是本周任务的下面的所有任务组成的list, 种类先设计一个函数专门用于解析文本的

    def parseSection(text:str):
        # splitlines是根据换行符隔开把文本拆成list
        # (text or "")如果text是真的, 那么返回text,如果是false,那么则返回后面那个空字符串
        #     短路规则:
        # 1.	先计算 a
        # 2.	如果 a 是真值 → 直接返回 a（不会看 b）
        # 3.	如果 a 是假值 → 直接返回 b，不管 b 是真是假  
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        dateLabel = lines[0]
        day_lines, week_lines = [],[]

        for l in lines:
            if "任务" in l:
                if not l.startswith("本周"):
                    currentBlock = "week"
                else:
                    currentBlock = "day"
                continue
            if currentBlock == "day":
                day_lines.append(l)
            elif currentBlock == "week":
                week_lines.append(l)
        
        return dateLabel, day_lines, week_lines
    
    dateLabel, day_lines, week_lines = parseSection(summaryText)

    def parseLines(lineLists: list):
        items = []
        for ln in lineLists:
            user_id, taskDescription = ln.split(", ", 1)
            user_id_list = user_id.split(",")
            items.append([user_id_list, taskDescription])
        return items
    
    dayItems = parseLines(day_lines)
    weekItems = parseLines(week_lines)

    def make_task_line(task_line: list):

        if not isinstance(task_line,(list, tuple)) or len(task_line)< 2:
            raise ValueError(f"输入的参数不对,应该是2个元素的list: {task_line}")

        user_id_list, text = task_line
        line = [
            {"tag": "text", "text":"☐   ", "style":["italic"]},
            # {"tag": "at", "user_id": user_id},
            # {"tag": "text", "text":text, "style":["italic", "bold"]}
        ]

        for user_id in user_id_list:
            line.append({"tag": "at", "user_id": user_id})

        line.append({"tag": "text", "text":text, "style":["italic", "bold"]})

        return line
    
    content = None # 这里需要先赋值, 否则万一lines是空的, 会导致currentBlock没有被赋值, 这样在和“day” 或者 “week”在对比的时候报错.

    content = [[{"tag":"text","text":dateLabel,"style": ["bold"]}]]
    for items in dayItems:
        content.append(make_task_line(items))
    content.append([{"tag":"text","text":"本周任务","style": ["bold"]}])
    for items in weekItems:
        content.append(make_task_line(items))

    if not isinstance(content, (list, tuple)) or not all(isinstance(line, (list, tuple)) for line in content): # all(iterable) 会检查 可迭代对象（比如 list、tuple、set、生成器）中的所有元素，如果全部为真，返回 True，只要有一个为假，就返回 False。
        raise ValueError(f"content的格式不对, 应该是一个list里面有很多个list: {content}")

    return {
        "zh_cn":{
            "title":title,
            "content":content
        }
    }

def _ensure_chat_id(receive_id:str = None):
    # 基于 or 运算符的短路逻辑
    # •	如果 receive_id 有值（即非空字符串、非 None），那么 target_id 就取 receive_id 的值。
	# •	如果 receive_id 没有值（即 None 或空字符串），则 target_id 会取默认值 CHAT_ID。
    targetID = receive_id or CHAT_ID

    logging.debug(f'chat id: {targetID}')

    if not targetID:
        raise ValueError(f'there is no chat id input or there is not 环境变量里面有chat_id')
    return targetID

def postText(*, tenant_access_token:str, receive_id_type:str="chat_id",zhObject:dict,receive_id:str):

    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {"Authorization": f"Bearer {tenant_access_token}", "Content-Type": "application/json"}
    params = {"receive_id_type": receive_id_type}
    payload = {
        "receive_id":receive_id,
        "msg_type":"post",
        "content":json.dumps(zhObject,ensure_ascii=False)
    }

    try:
        response = requests.post(url=url,headers=headers,params=params,json=payload,timeout=_HTTP_TIME_OUT)
    except requests.RequestException as e:
        raise Exception(f'发送消息的时候和服务器连接不上')
    
    if response.status_code == 200:

        try:
            data = response.json()
        except ValueError:
            raise Exception(f'无法解析为json: {response.text}')

        if data["code"] == 0:
            return True
        else:
            raise Exception(f'网络连接上了, 但是服务器的反应有问题: {data["msg"]}')
        
    else:
        raise Exception(f'http error, status code 不是200, 不知道什么原因 {response.status_code} - {response.text}')
    
def postMessage(summaryText):
    chatID=_ensure_chat_id()
    zhObject=createPost_zh_cn_Dic(summaryText=summaryText)
    tenant_access_token=get_tenant_access_token()
    print(tenant_access_token)
    postText(tenant_access_token=tenant_access_token,zhObject=zhObject,receive_id=chatID)


if __name__ == "__main__":
    try:

        # 输入调试信息，确保每个关键函数都执行
        summaryText = summaryText = """
        昨日任务:
        ou_dd62b0f0c5a1e99269b55104a234d27a,ou_cb3a7f8f4133a895db91931f121b0cc1, DTC Marker, Test 2, 已完成
        ou_cb3a7f8f4133a895db91931f121b0cc1, Xmas 2026, Test 3, 未完成

        本周任务:
        ou_cb3a7f8f4133a895db91931f121b0cc1, Xmas 2026, qq, 已完成"""
        logging.debug(f"summaryText: {summaryText}")

        # 调用 postMessage 函数
        postMessage(summaryText=summaryText)

        

    except Exception as e:
    # 如果发生任何异常，记录错误信息
        logging.error(f"发生错误: {e}")