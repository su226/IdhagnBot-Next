from datetime import datetime, timezone

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import Adapter, MessageEvent
from nonebot.adapters.onebot.v11 import Bot as OBBot
from nonebot.adapters.onebot.v11 import Event as OBEvent
from nonebot.adapters.onebot.v11.event import Reply as OBReply
from pydantic import BaseModel

from idhagnbot.message.common import (
  EVENT_TIME_REGISTRY,
  MESSAGE_ID_REGISTRY,
  REPLY_INFO_REGISTRY,
  SENT_MESSAGE_ID_REGISTRY,
  ReplyInfo,
  unimsg_of,
)
from idhagnbot.onebot import LAGRANGE, get_implementation

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Reply
from nonebot_plugin_alconna.uniseg import Receipt


async def message_id(bot: Bot, event: Event) -> str | None:
  if isinstance(event, MessageEvent):
    return str(event.message_id)
  return None


async def event_time(bot: Bot, event: Event) -> datetime | None:
  assert isinstance(event, OBEvent)
  return datetime.fromtimestamp(event.time)


async def reply_info(bot: Bot, event: Event, reply: Reply) -> ReplyInfo | None:
  assert isinstance(bot, OBBot)
  assert isinstance(reply.origin, OBReply)
  assert reply.origin.sender.user_id
  time = datetime.fromtimestamp(reply.origin.time)
  if await get_implementation(bot) == LAGRANGE:
    # https://github.com/LagrangeDev/Lagrange.Core/issues/897
    time = datetime.fromtimestamp(time.replace(tzinfo=timezone.utc).timestamp())
  return ReplyInfo(
    str(reply.origin.message_id),
    time,
    str(reply.origin.sender.user_id),
    unimsg_of(reply.origin.message, bot),
  )


class SendMessageResult(BaseModel):
  message_id: int


async def sent_message_id(receipt: Receipt) -> list[str]:
  result = list[str]()
  for msg_id in receipt.msg_ids:
    send_result = SendMessageResult.model_validate(msg_id)
    result.append(str(send_result.message_id))
  return result


def register() -> None:
  name = Adapter.get_name()
  MESSAGE_ID_REGISTRY[name] = message_id
  EVENT_TIME_REGISTRY[name] = event_time
  REPLY_INFO_REGISTRY[name] = reply_info
  SENT_MESSAGE_ID_REGISTRY[name] = sent_message_id
