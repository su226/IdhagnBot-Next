from datetime import datetime
from typing import Optional

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.satori import Adapter
from nonebot.adapters.satori.event import Event as SatoriEvent
from nonebot.adapters.satori.models import MessageReceipt

from idhagnbot.message.common import (
  EVENT_TIME_REGISTRY,
  MESSAGE_ID_REGISTRY,
  SENT_MESSAGE_ID_REGISTRY,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Receipt


async def message_id(bot: Bot, event: Event) -> Optional[str]:
  assert isinstance(event, SatoriEvent)
  return event.message.id if event.message else None


async def event_time(bot: Bot, event: Event) -> Optional[datetime]:
  assert isinstance(event, SatoriEvent)
  return event.timestamp


async def sent_message_id(receipt: Receipt) -> list[str]:
  result = []
  for msg_id in receipt.msg_ids:
    assert isinstance(msg_id, MessageReceipt)
    result.append(msg_id.id)
  return result


def register() -> None:
  name = Adapter.get_name()
  MESSAGE_ID_REGISTRY[name] = message_id
  EVENT_TIME_REGISTRY[name] = event_time
  SENT_MESSAGE_ID_REGISTRY[name] = sent_message_id
