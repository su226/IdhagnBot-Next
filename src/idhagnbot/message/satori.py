from datetime import datetime

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.satori import Adapter, Message, MessageEvent
from nonebot.adapters.satori import Bot as SatoriBot
from nonebot.adapters.satori.element import parse
from nonebot.adapters.satori.event import Event as SatoriEvent
from nonebot.adapters.satori.message import RenderMessage
from nonebot.adapters.satori.models import MessageReceipt

from idhagnbot.message.common import (
  EVENT_TIME_REGISTRY,
  MESSAGE_ID_REGISTRY,
  REPLY_INFO_REGISTRY,
  SENT_MESSAGE_ID_REGISTRY,
  ReplyInfo,
  unimsg_of,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Reply
from nonebot_plugin_alconna.uniseg import Receipt


async def message_id(bot: Bot, event: Event) -> str | None:
  assert isinstance(event, SatoriEvent)
  return event.message.id if event.message else None


async def event_time(bot: Bot, event: Event) -> datetime | None:
  assert isinstance(event, SatoriEvent)
  return event.timestamp


async def reply_info(bot: Bot, event: Event, reply: Reply) -> ReplyInfo | None:
  assert isinstance(bot, SatoriBot)
  assert isinstance(reply.origin, RenderMessage)
  assert isinstance(event, MessageEvent)
  message_id = reply.origin.data.get("id")
  assert message_id
  message = await bot.message_get(channel_id=event.channel.id, message_id=message_id)
  assert message.created_at
  assert message.user
  content = unimsg_of(Message.from_satori_element(parse(message.content)), bot)
  return ReplyInfo(message.id, message.created_at, message.user.id, content)


async def sent_message_id(receipt: Receipt) -> list[str]:
  result = list[str]()
  for msg_id in receipt.msg_ids:
    assert isinstance(msg_id, MessageReceipt)
    result.append(msg_id.id)
  return result


def register() -> None:
  name = Adapter.get_name()
  MESSAGE_ID_REGISTRY[name] = message_id
  EVENT_TIME_REGISTRY[name] = event_time
  REPLY_INFO_REGISTRY[name] = reply_info
  SENT_MESSAGE_ID_REGISTRY[name] = sent_message_id
