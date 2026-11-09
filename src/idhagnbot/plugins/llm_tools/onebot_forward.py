import json
from io import StringIO
from typing import Any

from arclet.entari import Session
from entari_plugin_llm import register_tool


def get_qq_json_title(data: dict[str, Any]) -> str:
    try:
        app = data["meta"]["detail_1"]["title"]
        description = data["meta"]["detail_1"]["desc"]
    except KeyError:
        pass
    else:
        return f"[{app}]{description}"
    try:
        app = data["meta"]["news"]["tag"]
        description = data["meta"]["news"]["title"]
    except KeyError:
        pass
    else:
        return f"[{app}]{description}"
    try:
        prompt = data["prompt"]
    except KeyError:
        return ""
    return str(prompt)


def get_forward_info(node: dict[str, Any]) -> tuple[str, list[dict[str, Any]]] | None:
    try:
        # OneBot 标准（Lagrange.OneBot）
        return node["data"]["nickname"], node["data"]["content"]
    except KeyError:
        pass
    try:
        # NapCat / SnowLuma
        return node["sender"]["nickname"], node["message"]
    except KeyError:
        pass
    try:
        # go-cqhttp / LLBot
        return node["sender"]["nickname"], node["content"]
    except KeyError:
        pass
    return None


def parse_onebot_segments(segments: list[dict[str, Any]]) -> str:
    content = StringIO()
    for segment in segments:
        if segment["type"] == "text":
            content.write(segment["data"]["text"])
        elif segment["type"] == "face":
            content.write("[表情]")
        elif segment["type"] == "image":
            content.write(f"[图片 url={segment['data']['url']}]")
        elif segment["type"] == "record":
            content.write("[语音]")
        elif segment["type"] == "video":
            content.write("[视频]")
        elif segment["type"] == "at":
            if "name" in segment["data"]:  # go-cqhttp / LLBot
                at_name = segment["data"]["name"].lstrip("@")
                content.write(f"@{at_name} ")
            else:
                content.write("@未知成员 ")
        elif segment["type"] == "rps":
            content.write("[猜拳]")
        elif segment["type"] == "dice":
            content.write("[骰子]")
        elif segment["type"] == "shake":
            content.write("[窗口抖动]")
        elif segment["type"] == "poke":
            content.write("[戳一戳]")
        elif segment["type"] == "share":
            content.write("[分享]")
        elif segment["type"] == "contact":
            if segment["data"]["type"] == "qq":
                content.write("[推荐好友]")
            else:
                content.write("[推荐群]")
        elif segment["type"] == "location":
            content.write("[位置]")
        elif segment["type"] == "reply":
            if "message" in segment["data"]:  # NapCat / SnowLuma
                reply_segments = segment["data"]["message"]
                content.write(f"[回复: {parse_onebot_segments(reply_segments)}]")
            else:
                content.write("[回复]")
        elif segment["type"] == "forward":
            content.write(f"[合并转发 id={segment['data']['id']}]")
        elif segment["type"] == "xml":
            content.write("[卡片消息]")
        elif segment["type"] == "json":
            json_title = get_qq_json_title(json.loads(segment["data"]["data"]))
            if json_title:
                content.write(f"[卡片消息 {json_title}]")
            else:
                content.write("[卡片消息]")
        else:
            content.write("[未知消息]")
    return content.getvalue()


@register_tool
async def view_onebot_forward(session: Session, id: str) -> str:
    """
    查看合并转发，当你遇到 onebot:forward 标签时，可使用其中的 id 属性查看合并转发。
    合并转发可能嵌套，可以继续调用本工具查看。

    Args:
        session (Session): 当前会话对象
        id (str): 合并转发 ID。

    Returns:
        str: 成功时返回合并转发内容，失败时返回错误详情。
    """
    if session.account.adapter != "onebot":
        return "当前适配器不支持查看合并转发"
    try:
        message = await session.account.internal("get_forward_msg", id=id)
    except Exception:
        return "查看合并转发失败，可能是 ID 无效或已过期。"
    contents = []
    # message：OneBot 标准（Lagrange.OneBot）
    # messages：go-cqhttp / NapCat / SnowLuma / LLBot
    messages = message.get("message") or message.get("messages")
    if messages is None:
        return "当前协议端不支持查看合并转发"
    for node in messages:
        info = get_forward_info(node)
        if not info:
            return "当前协议端不支持查看合并转发"
        name, segments = info
        content = parse_onebot_segments(segments)
        contents.append(f"{name}: {content}")
    return "\n".join(contents)
