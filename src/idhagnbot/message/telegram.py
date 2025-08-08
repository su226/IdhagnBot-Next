import asyncio
from datetime import datetime, timezone
from itertools import chain
from typing import Optional, cast

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.telegram import Adapter, Message, MessageSegment
from nonebot.adapters.telegram.event import MessageEvent
from typing_extensions import TypeGuard

from idhagnbot.message.common import MERGED_EVENT_REGISTRY, MERGED_MSG_REGISTRY

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, UniMessage

media_groups = dict[str, tuple[datetime, list[MessageEvent]]]()


async def merged_event(bot: Bot, event: Event) -> Optional[list[Event]]:
  if not isinstance(event, MessageEvent) or not event.media_group_id:
    return [event]
  now = datetime.now(timezone.utc)
  _, events = media_groups.setdefault(event.media_group_id, (now, []))
  events.append(event)
  media_groups[event.media_group_id] = (now, events)
  await asyncio.sleep(0.1)
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


def register() -> None:
  name = Adapter.get_name()
  MERGED_EVENT_REGISTRY[name] = merged_event
  MERGED_MSG_REGISTRY[name] = merged_msg
