import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent
from nonebot.adapters.onebot.v11 import Bot as OBBot
from PIL import Image
from yarl import URL

from idhagnbot.image import open_url
from idhagnbot.onebot import get_rkey_cached
from idhagnbot.plugins.quote.common import (
  EMOJI_REGISTRY,
  MESSAGE_PROCESSOR_REGISTRY,
  USER_INFO_REGISTRY,
  UserInfo,
)

nonebot.require("nonebot_plugin_alconna")
nonebot.require("idhagnbot.plugins.chat_record")
from nonebot_plugin_alconna import Image as ImageSeg
from nonebot_plugin_alconna import Segment, UniMessage


async def get_user_info(bot: Bot, event: Event, user_id: str) -> UserInfo:
  assert isinstance(bot, OBBot)
  if isinstance(event, GroupMessageEvent):
    info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(user_id))
    name = info["card"] or info["nickname"]
  else:
    info = await bot.get_stranger_info(user_id=int(user_id))
    name = info["nickname"]
  avatar = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=100"
  return UserInfo(name, avatar)


async def process_message(
  bot: Bot,
  event: Event,
  message: UniMessage[Segment],
) -> UniMessage[Segment]:
  if ImageSeg in message:
    assert isinstance(bot, OBBot)
    rkeys = await get_rkey_cached(bot)
    rkey = rkeys["group" if isinstance(event, GroupMessageEvent) else "private"]
    for image in message[ImageSeg]:
      if image.url:
        image.url = str(URL(image.url).update_query(rkey=rkey.rkey))
  return message


async def fetch_emoji(bot: Bot, emoji_id: str) -> Image.Image:
  return await open_url(f"https://koishi.js.org/QFace/static/s{emoji_id}.png")


def register() -> None:
  name = Adapter.get_name()
  USER_INFO_REGISTRY[name] = get_user_info
  MESSAGE_PROCESSOR_REGISTRY[name] = process_message
  EMOJI_REGISTRY[name] = fetch_emoji
