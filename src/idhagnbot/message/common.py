from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.params import Depends

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Reply, Segment, UniMessage, UniversalMessage
from nonebot_plugin_alconna.uniseg import Receipt


@dataclass
class ReplyInfo:
  id: str
  time: datetime
  user_id: str
  message: UniMessage[Segment]


MERGED_EVENT_REGISTRY = dict[str, Callable[[Bot, Event], Awaitable[list[Event] | None]]]()
MERGED_MSG_REGISTRY = dict[
  str,
  Callable[[Bot, list[Event], UniMessage[Segment]], Awaitable[UniMessage[Segment] | None]],
]()
ORIG_MERGED_MSG_REGISTRY = dict[
  str,
  Callable[[Bot, list[Event], UniMessage[Segment]], Awaitable[UniMessage[Segment] | None]],
]()
MESSAGE_ID_REGISTRY = dict[str, Callable[[Bot, Event], Awaitable[str | None]]]()
EVENT_TIME_REGISTRY = dict[str, Callable[[Bot, Event], Awaitable[datetime | None]]]()
REPLY_INFO_REGISTRY = dict[str, Callable[[Bot, Event, Reply], Awaitable[ReplyInfo | None]]]()
SENT_MESSAGE_ID_REGISTRY = dict[str, Callable[[Receipt], Awaitable[list[str]]]]()
UniMsg = Annotated[UniMessage[Segment], UniversalMessage()]
OrigUniMsg = Annotated[UniMessage[Segment], UniversalMessage(origin=True)]


async def merged_event(bot: Bot, event: Event) -> list[Event] | None:
  if handler := MERGED_EVENT_REGISTRY.get(bot.adapter.get_name()):
    return await handler(bot, event)
  return [event]


MergedEvent = Annotated[list[Event], Depends(merged_event)]


async def merged_msg(bot: Bot, events: MergedEvent, msg: UniMsg) -> UniMessage[Segment] | None:
  if handler := MERGED_MSG_REGISTRY.get(bot.adapter.get_name()):
    return await handler(bot, events, msg)
  return msg


MergedMsg = Annotated[UniMessage[Segment], Depends(merged_msg)]


async def orig_merged_msg(
  bot: Bot,
  events: MergedEvent,
  msg: OrigUniMsg,
) -> UniMessage[Segment] | None:
  if handler := ORIG_MERGED_MSG_REGISTRY.get(bot.adapter.get_name()):
    return await handler(bot, events, msg)
  return msg


OrigMergedMsg = Annotated[UniMessage[Segment], Depends(orig_merged_msg)]


async def message_id(bot: Bot, event: Event) -> str | None:
  if handler := MESSAGE_ID_REGISTRY.get(bot.adapter.get_name()):
    return await handler(bot, event)
  return None


MessageId = Annotated[str, Depends(message_id)]


async def event_time(bot: Bot, event: Event) -> datetime:
  if (handler := EVENT_TIME_REGISTRY.get(bot.adapter.get_name())) and (
    time := await handler(bot, event)
  ):
    return time
  if time := getattr(event, "__idhagnbot_time__", None):
    return time
  time = datetime.now()
  setattr(event, "__idhagnbot_time__", time)
  return time


EventTime = Annotated[datetime, Depends(event_time)]


async def reply_info(bot: Bot, event: Event, message: OrigUniMsg) -> ReplyInfo | None:
  handler = REPLY_INFO_REGISTRY.get(bot.adapter.get_name())
  if not handler:
    return None
  reply = message[Reply]
  if not reply:
    return None
  return await handler(bot, event, reply[0])


MaybeReplyInfo = Annotated[ReplyInfo | None, Depends(reply_info)]


async def send_message(message: UniMessage[Any]) -> list[str]:
  receipt = await message.send()
  if handler := SENT_MESSAGE_ID_REGISTRY.get(receipt.bot.adapter.get_name()):
    return await handler(receipt)
  return []
