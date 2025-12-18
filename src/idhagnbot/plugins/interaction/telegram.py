import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.telegram import Adapter
from nonebot.adapters.telegram.event import (
  ChannelPostEvent,
  GroupMessageEvent,
  PrivateMessageEvent,
)
from nonebot.adapters.telegram.model import Chat

from idhagnbot.plugins.interaction.common import AT_EXTRACT_REGISTRY, REPLY_EXTRACT_REGISTRY

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import At, Reply


async def extract_from_reply(bot: Bot, event: Event, reply: Reply) -> str:
  if isinstance(reply.origin, PrivateMessageEvent):
    sender = reply.origin.from_
  elif isinstance(reply.origin, GroupMessageEvent):
    sender = reply.origin.sender_chat or reply.origin.from_
  elif isinstance(reply.origin, ChannelPostEvent):
    sender = reply.origin.sender_chat or reply.origin.chat
  else:
    raise TypeError("未知消息来源类型")
  if isinstance(sender, Chat) and sender.title:
    return sender.title
  if sender.last_name:
    return f"{sender.first_name} {sender.last_name}"
  if sender.first_name:
    return sender.first_name
  if sender.username:
    return sender.username
  return str(sender.id)


async def extract_from_at(bot: Bot, event: Event, at: At) -> str:
  if at.display:  # 有 display 时是 text_mention，否则是 mention
    return at.display
  return at.target[1:]  # Bot API 无法从用户名获取用户信息


def register() -> None:
  adapter = Adapter.get_name()
  REPLY_EXTRACT_REGISTRY[adapter] = extract_from_reply
  AT_EXTRACT_REGISTRY[adapter] = extract_from_at
