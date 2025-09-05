from typing import Any, Optional

import nonebot
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import Adapter, Message, MessageSegment
from pydantic import TypeAdapter

from idhagnbot.hook.common import (
  CALLED_API_REGISTRY,
  CALLING_API_REGISTRY,
  call_message_send_failed_hook,
  call_message_sending_hook,
  call_message_sent_hook,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, SupportScope, Target, UniMessage


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
  bot: Bot,
  api: str,
  data: dict[str, Any],
) -> Optional[tuple[UniMessage[Segment], Target]]:
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
  return UniMessage.of(message, bot), target


async def on_calling_api(bot: Bot, api: str, data: dict[str, Any]) -> None:
  if parsed := _parse_from_data(bot, api, data):
    message, target = parsed
    await call_message_sending_hook(bot, message, target)


async def on_called_api(
  bot: Bot,
  e: Optional[Exception],
  api: str,
  data: dict[str, Any],
  result: Any,
) -> None:
  if parsed := _parse_from_data(bot, api, data):
    message, target = parsed
    if e:
      await call_message_send_failed_hook(bot, message, target, e)
    else:
      await call_message_sent_hook(bot, message, target, [str(result["message_id"])])


def register() -> None:
  CALLING_API_REGISTRY[Adapter.get_name()] = on_calling_api
  CALLED_API_REGISTRY[Adapter.get_name()] = on_called_api
