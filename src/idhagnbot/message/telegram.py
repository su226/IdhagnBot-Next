from datetime import datetime, timezone
from itertools import chain
from typing import Optional, cast

import anyio
import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.telegram import Adapter, Message, MessageSegment
from nonebot.adapters.telegram.event import EditedMessageEvent, MessageEvent
from nonebot.adapters.telegram.model import Message as RawMessage
from typing_extensions import TypeGuard

from idhagnbot.message.common import (
  EVENT_TIME_REGISTRY,
  MERGED_EVENT_REGISTRY,
  MERGED_MSG_REGISTRY,
  MESSAGE_ID_REGISTRY,
  ORIG_MERGED_MSG_REGISTRY,
  SENT_MESSAGE_ID_REGISTRY,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, UniMessage
from nonebot_plugin_alconna.uniseg import Receipt

media_groups = dict[str, tuple[datetime, list[MessageEvent]]]()


async def merged_event(bot: Bot, event: Event) -> Optional[list[Event]]:
  if not isinstance(event, MessageEvent) or not event.media_group_id:
    return [event]
  now = datetime.now(timezone.utc)
  _, events = media_groups.setdefault(event.media_group_id, (now, []))
  events.append(event)
  media_groups[event.media_group_id] = (now, events)
  await anyio.sleep(0.1)
  time, _ = media_groups[event.media_group_id]
  if time != now:
    return None
  del media_groups[event.media_group_id]
  events.sort(key=lambda event: event.message_id)
  return list(events)


def _is_message_events(events: list[Event]) -> TypeGuard[list[MessageEvent]]:
  return all(isinstance(event, MessageEvent) for event in events)


async def merged_msg(
  bot: Bot,
  events: list[Event],
  msg: UniMessage[Segment],
) -> Optional[UniMessage[Segment]]:
  if len(events) > 1 and _is_message_events(events):
    chained = chain.from_iterable(cast(Message[MessageSegment], event.message) for event in events)
    return UniMessage.of(Message(chained), bot)
  return msg


async def orig_merged_msg(
  bot: Bot,
  events: list[Event],
  msg: UniMessage[Segment],
) -> Optional[UniMessage[Segment]]:
  if len(events) > 1 and _is_message_events(events):
    chained = chain.from_iterable(
      cast(Message[MessageSegment], event.original_message) for event in events
    )
    return UniMessage.of(Message(chained), bot)
  return msg


async def message_id(bot: Bot, event: Event) -> Optional[str]:
  if isinstance(event, MessageEvent):
    return str(event.message_id)
  return None


async def event_time(bot: Bot, event: Event) -> Optional[datetime]:
  if isinstance(event, EditedMessageEvent):
    return datetime.fromtimestamp(event.edit_date)
  if date := getattr(event, "date", None):
    return datetime.fromtimestamp(date)
  return None


async def sent_message_id(receipt: Receipt) -> list[str]:
  result = []
  for msg_id in receipt.msg_ids:
    assert isinstance(msg_id, RawMessage)
    result.append(msg_id.message_id)
  return result


def register() -> None:
  name = Adapter.get_name()
  MERGED_EVENT_REGISTRY[name] = merged_event
  MERGED_MSG_REGISTRY[name] = merged_msg
  ORIG_MERGED_MSG_REGISTRY[name] = orig_merged_msg
  MESSAGE_ID_REGISTRY[name] = message_id
  EVENT_TIME_REGISTRY[name] = event_time
  SENT_MESSAGE_ID_REGISTRY[name] = sent_message_id
