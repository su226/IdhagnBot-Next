import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.telegram import Adapter
from nonebot.adapters.telegram import Bot as TGBot
from nonebot.adapters.telegram.event import (
  ChannelPostEvent,
  GroupMessageEvent,
  PrivateMessageEvent,
)
from nonebot.adapters.telegram.model import Chat

from idhagnbot.plugins.interaction.common import REPLY_EXTRACT_REGISTRY

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Reply


async def extract(bot: Bot, event: Event, reply: Reply) -> str:
  assert isinstance(bot, TGBot)
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


def register() -> None:
  REPLY_EXTRACT_REGISTRY[Adapter.get_name()] = extract
