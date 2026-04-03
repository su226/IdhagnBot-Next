import math
from typing import Any, ClassVar
from uuid import UUID, uuid4

import nonebot
from anyio import Path
from anyio.to_thread import run_sync
from nonebot.adapters import Bot, Event
from nonebot.typing import T_State
from PIL import Image
from sqlalchemy import UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.command import CommandBuilder
from idhagnbot.context import SceneId
from idhagnbot.image import contain_down, paste, to_segment
from idhagnbot.itertools import batched
from idhagnbot.message import MaybeReplyInfo
from idhagnbot.text import render

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, image_fetch
from nonebot_plugin_alconna import Image as ImageSeg
from nonebot_plugin_localstore import get_data_dir
from nonebot_plugin_orm import Model, async_scoped_session


class Aspect(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_aspect_aspect"
  id: Mapped[UUID] = mapped_column(primary_key=True)
  scene_id: Mapped[str]
  title: Mapped[str]
  __table_args__: ClassVar[Any] = (UniqueConstraint("scene_id", "title"),)


COLUMNS = 5
IMAGE_SIZE = 100
TEXT_HEIGHT = 40
GAP = 10
MARGIN = 25
FONT_SIZE = 30
HEADER_FONT_SIZE = 50


show = (
  CommandBuilder()
  .node("aspect.show")
  .parser(Alconna("群要素", meta=CommandMeta("查看当前的群要素")))
  .build()
)


@show.handle()
async def _(scene_id: SceneId, sql: async_scoped_session) -> None:
  result = await sql.execute(select(Aspect).where(Aspect.scene_id == scene_id))
  aspects = result.scalars().all()

  if not aspects:
    await show.finish("还没有群要素")

  def make() -> ImageSeg:
    lines = math.ceil(len(aspects) / COLUMNS)
    header_im = render("群要素", "sans bold", HEADER_FONT_SIZE)
    width = MARGIN * 2 + max(header_im.width, COLUMNS * IMAGE_SIZE + (COLUMNS - 1) * MARGIN)
    height = MARGIN * 2 + header_im.height + lines * (IMAGE_SIZE + GAP + TEXT_HEIGHT + MARGIN)
    im = Image.new("RGB", (width, height), (255, 255, 255))
    paste(im, header_im, (width // 2, MARGIN), "mt")
    y = MARGIN * 2 + header_im.height
    image_dir = get_data_dir("idhagnbot") / "aspects"
    for line in batched(aspects, COLUMNS):
      x = MARGIN
      for aspect in line:
        aspect_im = Image.open(image_dir / str(aspect.id))
        aspect_im = contain_down(aspect_im, IMAGE_SIZE, IMAGE_SIZE)
        paste(im, aspect_im, (x + IMAGE_SIZE // 2, y + IMAGE_SIZE // 2), "mm")
        title_im = render(aspect.title, "sans", FONT_SIZE)
        title_im = contain_down(title_im, IMAGE_SIZE, TEXT_HEIGHT)
        paste(im, title_im, (x + IMAGE_SIZE // 2, y + IMAGE_SIZE + GAP), "mt")
        x += IMAGE_SIZE + MARGIN
      y += IMAGE_SIZE + GAP + TEXT_HEIGHT + MARGIN
    return to_segment(im)

  await show.finish(await run_sync(make))


add = (
  CommandBuilder()
  .node("aspect.add")
  .parser(
    Alconna(
      "添加群要素",
      Args["title", str],
      Args["image?", ImageSeg, None],
      meta=CommandMeta("又多了一个要素"),
    ),
  )
  .build()
)


@add.handle()
async def _(
  bot: Bot,
  event: Event,
  state: T_State,
  scene_id: SceneId,
  sql: async_scoped_session,
  title: str,
  image: ImageSeg | None,
  reply_info: MaybeReplyInfo,
) -> None:
  if image:
    image_seg = image
  elif reply_info and (reply_images := reply_info.message[ImageSeg]):
    image_seg = reply_images[0]
  else:
    await add.finish("没有传入图片")
  data = await image_fetch(event, bot, state, image_seg)
  if not data:
    await add.finish("无效图片")
  aspect = Aspect(id=uuid4(), scene_id=scene_id, title=title)
  sql.add(aspect)
  await sql.commit()
  image_dir = Path(get_data_dir("idhagnbot") / "aspects")
  await image_dir.mkdir(parents=True, exist_ok=True)
  async with await (image_dir / str(aspect.id)).open("wb") as f:
    await f.write(data)
  await remove.finish("要素已添加")


remove = (
  CommandBuilder()
  .node("aspect.remove")
  .parser(Alconna("删除群要素", Args["title", str], meta=CommandMeta("为什么少了一个要素")))
  .build()
)


@remove.handle()
async def _(title: str, scene_id: SceneId, sql: async_scoped_session) -> None:
  result = await sql.execute(
    select(Aspect).where(Aspect.scene_id == scene_id, Aspect.title == title),
  )
  aspect = result.scalar_one_or_none()
  if not aspect:
    await remove.finish("要素不存在")
  await sql.delete(aspect)
  await sql.commit()
  await Path(get_data_dir("idhagnbot") / "aspects" / str(aspect.id)).unlink(missing_ok=True)
  await remove.finish("要素已删除")
