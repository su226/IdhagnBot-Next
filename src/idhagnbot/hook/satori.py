from itertools import chain
from typing import Any, Optional

import nonebot
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters.satori import Adapter, Bot, Message
from nonebot.adapters.satori.models import ChannelType
from nonebot.exception import ActionFailed

from idhagnbot.hook.common import (
  CALLED_API_REGISTRY,
  CALLING_API_REGISTRY,
  call_message_send_failed_hook,
  call_message_sending_hook,
  call_message_sent_hook,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, SupportScope, Target, UniMessage


async def _parse_from_data(
  bot: BaseBot,
  api: str,
  data: dict[str, Any],
) -> Optional[tuple[UniMessage[Segment], Target]]:
  if api != "message_create":
    return None
  assert isinstance(bot, Bot)
  try:
    channel = await bot.channel_get(channel_id=data["channel_id"])
  except ActionFailed:
    return None
  parent_id = channel.parent_id or ""
  target = Target(
    channel.id,
    parent_id,
    parent_id not in ("", channel.id),
    channel.type == ChannelType.DIRECT,
    self_id=bot.self_id,
    scope=SupportScope.ensure_satori(bot.platform),
  )
  message = UniMessage.of(Message(data["content"]), bot)
  return message, target


async def on_calling_api(bot: BaseBot, api: str, data: dict[str, Any]) -> None:
  if parsed := await _parse_from_data(bot, api, data):
    message, target = parsed
    await call_message_sending_hook(bot, message, target)


async def on_called_api(
  bot: BaseBot,
  e: Optional[Exception],
  api: str,
  data: dict[str, Any],
  result: Any,
) -> None:
  if not e:
    if api != "message_create" or not result:
      return
    channel = result[0].channel
    assert isinstance(bot, Bot)
    if not channel:
      try:
        channel = await bot.channel_get(channel_id=data["channel_id"])
      except ActionFailed:
        return
    parent_id = channel.parent_id or ""
    target = Target(
      channel.id,
      parent_id,
      parent_id not in ("", channel.id),
      channel.type == ChannelType.DIRECT,
      self_id=bot.self_id,
      scope=SupportScope.ensure_satori(bot.platform),
    )
    chained = Message(chain.from_iterable(Message(message.content) for message in result))
    message = UniMessage.of(chained, bot)
    ids = [message.id for message in result]
    await call_message_sent_hook(bot, message, target, ids)
  elif parsed := await _parse_from_data(bot, api, data):
    message, target = parsed
    await call_message_send_failed_hook(bot, message, target, e)


def register() -> None:
  CALLING_API_REGISTRY[Adapter.get_name()] = on_calling_api
  CALLED_API_REGISTRY[Adapter.get_name()] = on_called_api
