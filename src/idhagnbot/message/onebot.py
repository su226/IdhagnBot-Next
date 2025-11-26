from datetime import datetime

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import Adapter, MessageEvent
from nonebot.adapters.onebot.v11 import Event as OBEvent
from pydantic import BaseModel

from idhagnbot.message.common import (
  EVENT_TIME_REGISTRY,
  MESSAGE_ID_REGISTRY,
  SENT_MESSAGE_ID_REGISTRY,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Receipt


async def message_id(bot: Bot, event: Event) -> str | None:
  if isinstance(event, MessageEvent):
    return str(event.message_id)
  return None


async def event_time(bot: Bot, event: Event) -> datetime | None:
  assert isinstance(event, OBEvent)
  return datetime.fromtimestamp(event.time)


class SendMessageResult(BaseModel):
  message_id: int


async def sent_message_id(receipt: Receipt) -> list[str]:
  result = []
  for msg_id in receipt.msg_ids:
    send_result = SendMessageResult.model_validate(msg_id)
    result.append(send_result.message_id)
  return result


def register() -> None:
  name = Adapter.get_name()
  MESSAGE_ID_REGISTRY[name] = message_id
  EVENT_TIME_REGISTRY[name] = event_time
  SENT_MESSAGE_ID_REGISTRY[name] = sent_message_id
