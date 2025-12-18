from pathlib import Path

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.telegram import Adapter
from nonebot.adapters.telegram import Bot as TGBot
from nonebot.adapters.telegram.model import ChatFullInfo
from PIL import Image

from idhagnbot.image import open_url
from idhagnbot.plugins.quote.common import (
  EMOJI_REGISTRY,
  USER_INFO_REGISTRY,
  UserInfo,
)

nonebot.require("nonebot_plugin_alconna")


def extract_name(sender: ChatFullInfo) -> tuple[str, str]:
  if sender.title:
    return sender.title, ""
  if sender.first_name:
    return sender.first_name, sender.last_name or ""
  if sender.username:
    return sender.username, ""
  return str(sender.id), ""


async def get_file_url(bot: TGBot, file_id: str) -> str | None:
  file = await bot.get_file(file_id)
  if not file.file_path:
    return None
  if (path := Path(file.file_path)).exists():
    return path.as_uri()
  return f"{bot.bot_config.api_server}file/bot{bot.bot_config.token}/{file.file_path}"


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


async def fetch_emoji(bot: Bot, emoji_id: str) -> Image.Image:
  assert isinstance(bot, TGBot)
  stickers = await bot.get_custom_emoji_stickers([emoji_id])
  assert stickers[0].thumbnail
  file = await bot.get_file(stickers[0].thumbnail.file_id)
  assert file.file_path
  if (path := Path(file.file_path)).exists():
    url = path.as_uri()
  else:
    url = f"{bot.bot_config.api_server}file/bot{bot.bot_config.token}/{file.file_path}"
  return await open_url(url)


def register() -> None:
  name = Adapter.get_name()
  USER_INFO_REGISTRY[name] = get_user_info
  EMOJI_REGISTRY[name] = fetch_emoji
