from collections.abc import Awaitable, Callable
from typing import Annotated, Optional

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.params import Depends

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, UniMessage, UniversalMessage

MERGED_EVENT_REGISTRY = dict[str, Callable[[Bot, Event], Awaitable[Optional[list[Event]]]]]()
MERGED_MSG_REGISTRY = dict[
  str,
  Callable[[Bot, list[Event], UniMessage[Segment]], Awaitable[Optional[UniMessage[Segment]]]],
]()
UniMsg = Annotated[UniMessage[Segment], UniversalMessage()]


async def merged_event(bot: Bot, event: Event) -> Optional[list[Event]]:
  if handler := MERGED_EVENT_REGISTRY.get(bot.adapter.get_name()):
    return await handler(bot, event)
  return [event]


MergedEvent = Annotated[list[Event], Depends(merged_event)]


async def merged_msg(bot: Bot, events: MergedEvent, msg: UniMsg) -> Optional[UniMessage[Segment]]:
  if handler := MERGED_MSG_REGISTRY.get(bot.adapter.get_name()):
    return await handler(bot, events, msg)
  return msg


MergedMsg = Annotated[UniMessage[Segment], Depends(merged_msg)]
