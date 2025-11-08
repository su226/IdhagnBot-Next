import asyncio
from datetime import datetime, timezone
from io import BytesIO

import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent, Message
from nonebot.adapters.onebot.v11 import Bot as OBBot
from nonebot.adapters.onebot.v11.event import Reply as OBReply
from PIL import Image
from yarl import URL

from idhagnbot.http import get_session
from idhagnbot.onebot import LAGRANGE, get_implementation, get_rkey_cached
from idhagnbot.plugins.quote.common import (
  EMOJI_REGISTRY,
  MESSAGE_PROCESSOR_REGISTRY,
  REPLY_EXTRACT_REGISTRY,
  USER_INFO_REGISTRY,
  MessageInfo,
  ReplyInfo,
  UserInfo,
)

nonebot.require("nonebot_plugin_alconna")
nonebot.require("idhagnbot.plugins.chat_record")
from nonebot_plugin_alconna import Image as ImageSeg
from nonebot_plugin_alconna import Reply, Segment, UniMessage


async def extract_from_reply(bot: Bot, event: Event, reply: Reply) -> ReplyInfo:
  assert isinstance(bot, OBBot)
  assert isinstance(reply.msg, Message)
  assert isinstance(reply.origin, OBReply)
  user_id = reply.origin.sender.user_id
  assert user_id
  time = datetime.fromtimestamp(reply.origin.time)
  if await get_implementation(bot) == LAGRANGE:
    time = datetime.fromtimestamp(time.replace(tzinfo=timezone.utc).timestamp())
  return ReplyInfo(
    reply.id,
    time,
    MessageInfo(str(user_id), UniMessage.of(reply.msg)),
  )


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


def open_emoji(data: bytes) -> Image.Image:
  return Image.open(BytesIO(data))


async def fetch_emoji(bot: Bot, id: str) -> Image.Image:
  async with get_session().get(f"https://koishi.js.org/QFace/static/s{id}.png") as response:
    return await asyncio.to_thread(open_emoji, await response.read())


def register() -> None:
  name = Adapter.get_name()
  REPLY_EXTRACT_REGISTRY[name] = extract_from_reply
  USER_INFO_REGISTRY[name] = get_user_info
  MESSAGE_PROCESSOR_REGISTRY[name] = process_message
  EMOJI_REGISTRY[name] = fetch_emoji
