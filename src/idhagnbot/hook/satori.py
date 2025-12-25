from datetime import datetime
from typing import Any

import nonebot
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters.satori import Adapter, Bot, Message
from nonebot.adapters.satori.models import ChannelType, MessageReceipt
from nonebot.exception import ActionFailed

from idhagnbot.asyncio import gather_seq
from idhagnbot.hook.common import (
  CALLED_API_REGISTRY,
  CALLING_API_REGISTRY,
  SentMessage,
  call_message_send_failed_hook,
  call_message_sending_hook,
  call_message_sent_hook,
)
from idhagnbot.message import unimsg_of

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, SupportScope, Target, UniMessage


async def _parse_target_from_id(channel_id: str, bot: Bot) -> Target:
  try:
    channel = await bot.channel_get(channel_id=channel_id)
    is_private = channel.type == ChannelType.DIRECT
  except ActionFailed:
    is_private = False
  if is_private:
    is_channel = False
  else:
    try:
      await bot.guild_get(guild_id=channel_id)
      is_channel = False
    except ActionFailed:
      is_channel = True
  return Target(
    channel_id,
    "",  # Satori 无法从 channel_id 获取 guild_id
    is_channel,
    is_private,
    self_id=bot.self_id,
    scope=SupportScope.ensure_satori(bot.platform),
  )


async def _parse_target_from_receipt(receipt: MessageReceipt, bot: Bot) -> Target | None:
  channel = receipt.channel
  if not channel:
    return None
  is_private = channel.type == ChannelType.DIRECT
  guild = receipt.guild
  if guild:
    guild_id = guild.id
    is_channel = channel.id != guild_id
  elif is_private:
    guild_id = ""
    is_channel = False
  else:
    guild_id = ""
    try:
      await bot.guild_get(guild_id=channel.id)
      is_channel = False
    except ActionFailed:
      is_channel = True
  return Target(
    channel.id,
    guild_id,
    is_channel,
    is_private,
    self_id=bot.self_id,
    scope=SupportScope.ensure_satori(bot.platform),
  )


async def _parse_from_data(
  bot: BaseBot,
  api: str,
  data: dict[str, Any],
) -> tuple[UniMessage[Segment], Target] | None:
  if api != "message_create":
    return None
  message = unimsg_of(Message(data["content"]), bot)
  assert isinstance(bot, Bot)
  return message, await _parse_target_from_id(data["channel_id"], bot)


async def _parse_sent_message(
  message: MessageReceipt,
  channel_id: str,
  date: datetime,
  bot: Bot,
) -> SentMessage:
  content = message.content
  created_at = message.created_at
  if not content or not created_at:
    fetched = await bot.message_get(channel_id=channel_id, message_id=message.id)
    content = content or fetched.content
    created_at = created_at or fetched.created_at
  if not created_at:
    created_at = date
  return SentMessage(created_at, message.id, unimsg_of(Message(content), bot))


async def on_calling_api(bot: BaseBot, api: str, data: dict[str, Any]) -> None:
  if parsed := await _parse_from_data(bot, api, data):
    message, target = parsed
    await call_message_sending_hook(bot, message, target)


async def on_called_api(
  bot: BaseBot,
  e: Exception | None,
  api: str,
  data: dict[str, Any],
  result: Any,
) -> None:
  if not e:
    if api != "message_create" or not result:
      return
    date = datetime.now()
    assert isinstance(bot, Bot)
    channel_id = data["channel_id"]
    target = await _parse_target_from_receipt(result[0], bot)
    if not target:
      target = await _parse_target_from_id(channel_id, bot)
    message = unimsg_of(Message(data["content"]), bot)
    messages = await gather_seq(
      _parse_sent_message(message, channel_id, date, bot) for message in result
    )
    await call_message_sent_hook(bot, message, list(messages), target)
  elif parsed := await _parse_from_data(bot, api, data):
    message, target = parsed
    await call_message_send_failed_hook(bot, message, target, e)


def register() -> None:
  CALLING_API_REGISTRY[Adapter.get_name()] = on_calling_api
  CALLED_API_REGISTRY[Adapter.get_name()] = on_called_api
