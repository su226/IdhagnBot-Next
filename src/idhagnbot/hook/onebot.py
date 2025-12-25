import base64
from datetime import datetime
from typing import Any

import nonebot
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters.onebot.v11 import Adapter, Bot, Message, MessageSegment
from pydantic import TypeAdapter

from idhagnbot.hook.common import (
  CALLED_API_REGISTRY,
  CALLING_API_REGISTRY,
  SentMessage,
  call_message_send_failed_hook,
  call_message_sending_hook,
  call_message_sent_hook,
)
from idhagnbot.message import unimsg_of
from idhagnbot.url import path_from_url

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, SupportScope, Target, UniMessage
from nonebot_plugin_alconna.uniseg.segment import Media


def _normalize_message(raw: Any) -> Message:
  if isinstance(raw, Message):
    message = raw
  elif isinstance(raw, MessageSegment):
    message = Message(raw)
  else:
    message = TypeAdapter(Message).validate_python(raw)
  for seg in message:
    if seg.type == "node" and "content" in seg.data:
      seg.data["content"] = _normalize_message(seg.data["content"])
  return message


def _parse_from_data(
  bot: BaseBot,
  api: str,
  data: dict[str, Any],
) -> tuple[UniMessage[Segment], Target] | None:
  if api in ("send_private_msg", "send_group_msg", "send_msg"):
    message = data["message"]
  elif api in ("send_private_forward_msg", "send_group_forward_msg", "send_forward_msg"):
    message = data["messages"]
  else:
    return None
  message = _normalize_message(message)
  if "group_id" in data:
    target = Target(
      str(data["group_id"]),
      adapter=type(bot.adapter),
      self_id=bot.self_id,
      scope=SupportScope.qq_client,
    )
  else:
    target = Target(
      str(data["user_id"]),
      private=True,
      adapter=type(bot.adapter),
      self_id=bot.self_id,
      scope=SupportScope.qq_client,
    )
  message = unimsg_of(message, bot)
  for i in message[Media]:
    if i.id:
      if i.id.startswith("base64://"):
        i.raw = base64.b64decode(i.id[9:])
        i.id = None
        i.url = None
      elif i.id.startswith("file://"):
        i.path = path_from_url(i.id)
        i.id = None
        i.url = None
  return message, target


async def on_calling_api(bot: BaseBot, api: str, data: dict[str, Any]) -> None:
  if parsed := _parse_from_data(bot, api, data):
    message, target = parsed
    await call_message_sending_hook(bot, message, target)


async def on_called_api(
  bot: BaseBot,
  e: Exception | None,
  api: str,
  data: dict[str, Any],
  result: Any,
) -> None:
  if parsed := _parse_from_data(bot, api, data):
    message, target = parsed
    if e:
      await call_message_send_failed_hook(bot, message, target, e)
    else:
      assert isinstance(bot, Bot)
      message_id = result["message_id"]
      fetched = await bot.get_msg(message_id=message_id)
      messages = [
        SentMessage(
          datetime.now(),
          str(message_id),
          unimsg_of(_normalize_message(fetched["message"]), bot),
        ),
      ]
      await call_message_sent_hook(bot, message, messages, target)


def register() -> None:
  CALLING_API_REGISTRY[Adapter.get_name()] = on_calling_api
  CALLED_API_REGISTRY[Adapter.get_name()] = on_called_api
