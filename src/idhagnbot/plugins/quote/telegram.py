import asyncio
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.telegram import Adapter, Message
from nonebot.adapters.telegram import Bot as TGBot
from nonebot.adapters.telegram.event import (
  ChannelPostEvent,
  GroupMessageEvent,
  PrivateMessageEvent,
)
from nonebot.adapters.telegram.model import ChatFullInfo
from PIL import Image

from idhagnbot.http import get_session
from idhagnbot.plugins.quote.common import (
  EMOJI_REGISTRY,
  REPLY_EXTRACT_REGISTRY,
  USER_INFO_REGISTRY,
  MessageInfo,
  ReplyInfo,
  UserInfo,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Reply, UniMessage


def extract_name(sender: ChatFullInfo) -> tuple[str, str]:
  if sender.title:
    return sender.title, ""
  if sender.first_name:
    return sender.first_name, sender.last_name or ""
  if sender.username:
    return sender.username, ""
  return str(sender.id), ""


async def get_file_url(bot: TGBot, file_id: str) -> Optional[str]:
  file = await bot.get_file(file_id)
  if not file.file_path:
    return None
  if (path := Path(file.file_path)).exists():
    return path.as_uri()
  return f"{bot.bot_config.api_server}file/bot{bot.bot_config.token}/{file.file_path}"


async def extract_from_reply(bot: Bot, event: Event, reply: Reply) -> ReplyInfo:
  assert isinstance(reply.msg, Message)
  assert isinstance(bot, TGBot)
  if isinstance(reply.origin, PrivateMessageEvent):
    sender = reply.origin.from_
  elif isinstance(reply.origin, GroupMessageEvent):
    sender = reply.origin.sender_chat or reply.origin.from_
  elif isinstance(reply.origin, ChannelPostEvent):
    sender = reply.origin.sender_chat or reply.origin.chat
  else:
    raise TypeError("未知消息来源类型")
  return ReplyInfo(
    reply.id,
    datetime.fromtimestamp(reply.origin.date),
    MessageInfo(str(sender.id), UniMessage.of(reply.msg)),
  )


async def get_user_info(bot: Bot, event: Event, user_id: str) -> UserInfo:
  assert isinstance(bot, TGBot)
  chat = await bot.get_chat(int(user_id))
  first_name, last_name = extract_name(chat)
  if chat.photo and (url := await get_file_url(bot, chat.photo.small_file_id)):
    avatar = url
  elif last_name:
    avatar = f"avatar://{first_name[1]}{last_name[1]}"
  else:
    avatar = f"avatar://{first_name[1]}"
  name = f"{first_name} {last_name}" if last_name else first_name
  return UserInfo(name, avatar)


def open_emoji(data: bytes) -> Image.Image:
  return Image.open(BytesIO(data))


async def fetch_emoji(bot: Bot, id: str) -> Image.Image:
  assert isinstance(bot, TGBot)
  stickers = await bot.get_custom_emoji_stickers([id])
  assert stickers[0].thumbnail
  file = await bot.get_file(stickers[0].thumbnail.file_id)
  assert file.file_path
  if Path(file.file_path).exists():
    return Image.open(file.file_path)
  url = f"{bot.bot_config.api_server}file/bot{bot.bot_config.token}/{file.file_path}"
  async with get_session().get(url) as response:
    return await asyncio.to_thread(open_emoji, await response.read())


def register() -> None:
  name = Adapter.get_name()
  REPLY_EXTRACT_REGISTRY[name] = extract_from_reply
  USER_INFO_REGISTRY[name] = get_user_info
  EMOJI_REGISTRY[name] = fetch_emoji
