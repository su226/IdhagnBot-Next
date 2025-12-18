import random
from collections.abc import Awaitable, Sequence
from io import BytesIO
from itertools import dropwhile, islice
from typing import Any, ClassVar
from uuid import UUID, uuid4

import nonebot
from anyio.to_thread import run_sync
from nonebot.adapters import Bot, Event
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot import text
from idhagnbot.asyncio import gather, gather_map, gather_seq
from idhagnbot.color import split_rgb
from idhagnbot.command import CommandBuilder
from idhagnbot.context import SceneId
from idhagnbot.http import get_session
from idhagnbot.image import (
  circle,
  contain_down,
  get_scale_resample,
  paste,
  replace,
  rounded_rectangle,
  to_segment,
)
from idhagnbot.message import send_message, unimsg_load
from idhagnbot.message.common import REPLY_INFO_REGISTRY, MaybeReplyInfo
from idhagnbot.plugins.quote.common import (
  EMOJI_REGISTRY,
  MESSAGE_PROCESSOR_REGISTRY,
  USER_INFO_REGISTRY,
  MessageInfo,
  UserInfo,
)
from idhagnbot.url import path_from_url

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_localstore")
nonebot.require("nonebot_plugin_orm")
nonebot.require("idhagnbot.plugins.chat_record")
from nonebot_plugin_alconna import (
  Alconna,
  Args,
  CommandMeta,
  Emoji,
  Segment,
  Text,
  UniMessage,
  image_fetch,
)
from nonebot_plugin_alconna import Image as ImageSeg
from nonebot_plugin_localstore import get_data_dir
from nonebot_plugin_orm import Model, async_scoped_session

from idhagnbot.plugins.chat_record import Message

try:
  from idhagnbot.plugins.quote.onebot import register
except ImportError:
  pass
else:
  register()
try:
  from idhagnbot.plugins.quote.satori import register
except ImportError:
  pass
else:
  register()
try:
  from idhagnbot.plugins.quote.telegram import register
except ImportError:
  pass
else:
  register()


class SentQuote(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_quote_sent_quote"
  scene_id: Mapped[str] = mapped_column(primary_key=True)
  message_id: Mapped[str] = mapped_column(primary_key=True)
  quote_id: Mapped[UUID]


def generate_avatar(info: UserInfo) -> Image.Image:
  im = Image.new("RGB", (64, 64), split_rgb(info.color.avatar))
  text.paste(im, (32, 32), info.avatar[9:], "sans", 32, anchor="mm", color=0xFFFFFF)
  circle(im)
  return im


def open_avatar(info: UserInfo) -> Image.Image:
  im = Image.open(path_from_url(info.avatar)).resize((64, 64), get_scale_resample())
  circle(im)
  return im


def open_raw_avatar(data: bytes) -> Image.Image:
  im = Image.open(BytesIO(data)).resize((64, 64), get_scale_resample())
  circle(im)
  return im


async def fetch_avatar(info: UserInfo) -> Image.Image:
  if info.avatar.startswith("avatar://"):
    return await run_sync(generate_avatar, info)
  if info.avatar.startswith("file://"):
    return await run_sync(open_avatar, info)
  async with get_session().get(info.avatar) as response:
    return await run_sync(open_raw_avatar, await response.read())


async def fetch_avatars(users: dict[str, UserInfo]) -> dict[str, Image.Image]:
  return await gather_map({user_id: fetch_avatar(info) for user_id, info in users.items()})


async def fetch_image(bot: Bot, event: Event, segment: ImageSeg) -> None:
  segment.raw = await image_fetch(event, bot, {}, segment)


async def fetch_images(bot: Bot, event: Event, messages: Sequence[MessageInfo]) -> None:
  tasks = list[Awaitable[None]]()
  for message in messages:
    tasks.extend(fetch_image(bot, event, segment) for segment in message.message[ImageSeg])
  await gather_seq(tasks)


async def fetch_emojis(bot: Bot, messages: Sequence[MessageInfo]) -> dict[str, Image.Image]:
  fetch_emoji = EMOJI_REGISTRY.get(bot.adapter.get_name())
  if not fetch_emoji:
    return {}
  tasks = dict[str, Awaitable[Image.Image]]()
  for message in messages:
    for emoji in message.message[Emoji]:
      if emoji.id not in tasks:
        tasks[emoji.id] = fetch_emoji(bot, emoji.id)
  return await gather_map(tasks)


def render_content(
  message: UniMessage[Segment],
  emojis: dict[str, Image.Image],
  user: UserInfo | None,
) -> Image.Image:
  rows = list[Image.Image]()
  if user:
    rows.append(text.render(user.name, "sans bold", 32, color=user.color.name))

  buffer = text.RichText()
  buffer.set_font("sans", 32)
  buffer.set_width(640)
  empty = True

  def flush_buffer() -> None:
    nonlocal buffer, empty
    if not empty:
      rows.append(buffer.render(0xFFFFFF))
      buffer = text.RichText()
      buffer.set_font("sans", 32)
      buffer.set_width(640)
      empty = True

  for segment in message:
    if isinstance(segment, ImageSeg):
      flush_buffer()
      rows.append(contain_down(Image.open(BytesIO(segment.raw_bytes)), 640, 640))
    elif isinstance(segment, Text):
      buffer.append(segment.text)
      empty = False
    elif isinstance(segment, Emoji):
      if segment.id in emojis:
        buffer.append_image(emojis[segment.id])
      else:
        buffer.append("[emoji]")
      empty = False
    else:
      buffer.append(f"[{segment.type}]")
      empty = False
  flush_buffer()
  padding = 24
  width = max(im.width for im in rows) + padding * 2
  height = sum(im.height for im in rows) + padding * 2
  out_im = Image.new("RGB", (width, height), (45, 37, 55))
  y = padding
  for im in rows:
    paste(out_im, im, (padding, y))
    y += im.height
  rounded_rectangle(out_im, 32)
  return out_im


async def render_chat(
  bot: Bot,
  event: Event,
  messages: Sequence[MessageInfo],
  users: dict[str, UserInfo],
) -> Image.Image:
  avatars, _, emojis = await gather(
    fetch_avatars(users),
    fetch_images(bot, event, messages),
    fetch_emojis(bot, messages),
  )

  def make() -> Image.Image:
    nonlocal emojis
    emojis = {
      emoji_id: emoji.resize((40, 40), get_scale_resample()) for emoji_id, emoji in emojis.items()
    }
    contents = [
      render_content(
        message.message,
        emojis,
        users[message.user_id] if i == 0 or messages[i - 1].user_id != message.user_id else None,
      )
      for i, message in enumerate(messages)
    ]
    avatar_size = 64
    gap = 16
    gap_small = 4
    width = max(im.width for im in contents) + avatar_size + gap
    height = sum(im.height for im in contents)
    for i, message in enumerate(messages):
      if i != 0:
        height += gap if message.user_id != messages[i - 1].user_id else gap_small
    out_im = Image.new("RGBA", (width, height))
    y = 0
    for i, (message, im) in enumerate(zip(messages, contents, strict=True)):
      replace(out_im, im, (avatar_size + gap, y))
      y += im.height
      if i == len(messages) - 1 or messages[i + 1].user_id != message.user_id:
        replace(out_im, avatars[message.user_id], (0, y), anchor="lb")
        y += gap
      else:
        y += gap_small
    return out_im

  return await run_sync(make)


async def process_message(bot: Bot, event: Event, message: MessageInfo) -> MessageInfo:
  name = bot.adapter.get_name()
  if name in MESSAGE_PROCESSOR_REGISTRY:
    message.message = await MESSAGE_PROCESSOR_REGISTRY[name](bot, event, message.message)
  return message


async def get_user_info(bot: Bot, event: Event, user_id: str) -> tuple[str, UserInfo]:
  return user_id, await USER_INFO_REGISTRY[bot.adapter.get_name()](bot, event, user_id)


quote = (
  CommandBuilder()
  .node("quote.quote")
  .parser(Alconna("q", Args["count", int, 1], meta=CommandMeta("引用消息，aka. 入典")))
  .build()
)


@quote.handle()
async def _(
  *,
  bot: Bot,
  event: Event,
  count: int,
  reply_info: MaybeReplyInfo,
  scene_id: SceneId,
  sql: async_scoped_session,
) -> None:
  if bot.adapter.get_name() not in REPLY_INFO_REGISTRY:
    await quote.finish("抱歉，暂不支持当前平台")
  if not reply_info:
    await quote.finish("请回复一条消息")
  if count < 1 or count > 10:
    await quote.finish("只能引用 1 至 10 条消息")
  messages = [MessageInfo(reply_info.user_id, reply_info.message)]
  user_ids = {reply_info.user_id}
  if count > 1:
    records = await sql.scalars(
      select(Message)
      .where(Message.scene_id == scene_id, Message.time >= reply_info.time)
      # 如果平台时间戳为浮点型，几乎不会出现相同时间戳的情况
      # 但如果时间戳为整型，则可能出现相同时间戳，因此预留一定余量
      .limit(count + 10),
    )
    records = list(islice(dropwhile(lambda x: x.message_id != reply_info.id, records), 1, count))
    messages.extend(MessageInfo(x.user_id, unimsg_load(x.content)) for x in records)
    user_ids.update(x.user_id for x in records)
  messages, users = await gather(
    gather_seq(process_message(bot, event, message) for message in messages),
    gather_seq(get_user_info(bot, event, user_id) for user_id in user_ids),
  )
  im = await render_chat(bot, event, messages, dict(users))
  dirname = get_data_dir("idhagnbot") / "quote" / scene_id.replace(":", "__")
  dirname.mkdir(parents=True, exist_ok=True)
  quote_id = uuid4()
  im.save(dirname / f"{quote_id}.png")
  message_ids = await send_message(UniMessage(to_segment(im)))
  for message_id in message_ids:
    sql.add(SentQuote(scene_id=scene_id, message_id=message_id, quote_id=quote_id))
  await sql.commit()


random_quote = (
  CommandBuilder()
  .node("quote.random")
  .parser(Alconna("qrand", meta=CommandMeta("随机引用")))
  .build()
)


@random_quote.handle()
async def _(*, scene_id: SceneId, sql: async_scoped_session) -> None:
  dirname = get_data_dir("idhagnbot") / "quote" / scene_id.replace(":", "__")
  dirname.mkdir(parents=True, exist_ok=True)
  files = list(dirname.iterdir())
  if not files:
    await random_quote.finish("暂时没有引用")
  file = random.choice(files)
  quote_id = UUID(file.stem)
  message_ids = await send_message(UniMessage(ImageSeg(path=file)))
  for message_id in message_ids:
    sql.add(SentQuote(scene_id=scene_id, message_id=message_id, quote_id=quote_id))
  await sql.commit()


delete_quote = (
  CommandBuilder().node("quote.delete").parser(Alconna("qd", meta=CommandMeta("删除引用"))).build()
)


@delete_quote.handle()
async def _(
  *,
  bot: Bot,
  scene_id: SceneId,
  sql: async_scoped_session,
  reply_info: MaybeReplyInfo,
) -> None:
  if bot.adapter.get_name() not in REPLY_INFO_REGISTRY:
    await quote.finish("抱歉，暂不支持当前平台")
  if not reply_info:
    await quote.finish("请回复一条引用图片")
  sent_quote = await sql.get(SentQuote, (scene_id, reply_info.id))
  if not sent_quote:
    await quote.finish("请回复一条引用图片")
  dirname = get_data_dir("idhagnbot") / "quote" / scene_id.replace(":", "__")
  filename = dirname / f"{sent_quote.quote_id}.png"
  filename.unlink(missing_ok=True)
  await quote.finish("已删除当前引用")
