from collections.abc import Callable

import nonebot
from anyio.to_thread import run_sync
from PIL import Image, ImageOps

from idhagnbot import image
from idhagnbot.asyncio import gather
from idhagnbot.image.card import Card, CardAuthor, CardCover, CardText
from idhagnbot.plugins.bilibili_activity import extras
from idhagnbot.plugins.bilibili_activity.common import IMAGE_GAP, fetch_image, fetch_images
from idhagnbot.third_party.bilibili_activity import ActivityArticle
from idhagnbot.third_party.bilibili_activity.card import CardTopic

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Segment, Text, UniMessage


async def get_appender(activity: ActivityArticle[object]) -> Callable[[Card], None]:
  avatar, covers, append_extra = await gather(
    fetch_image(activity.avatar),
    fetch_images(*activity.content.covers),
    extras.format(activity.extra),
  )

  def appender(card: Card) -> None:
    nonlocal covers
    if len(covers) == 1:
      cover = covers[0]
    else:
      gaps = len(covers) - 1
      size = 640 - gaps * IMAGE_GAP
      covers = [ImageOps.fit(cover, (size, size), image.get_resample()) for cover in covers]
      cover = Image.new("RGB", (640, size), (255, 255, 255))
      for i, v in enumerate(covers):
        cover.paste(v, (i * (size + IMAGE_GAP), 0))
    block = Card()
    block.add(CardAuthor(avatar, activity.name))
    block.add(CardTopic(activity.topic))
    block.add(CardText(activity.content.title, size=40, lines=2))
    card.add(block)
    card.add(CardCover(cover, False))
    block = Card()
    block.add(CardText(activity.content.desc, size=32, lines=3))
    append_extra(block, False)
    card.add(block)

  return appender


async def format(activity: ActivityArticle[object], can_ignore: bool) -> UniMessage[Segment]:
  appender = await get_appender(activity)

  def make() -> UniMessage[Segment]:
    card = Card(0)
    appender(card)
    im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
    card.render(im, 0, 0)
    return UniMessage(
      [
        Text(f"{activity.name} 发布了专栏"),
        Text.br(),
        image.to_segment(im),
        Text.br(),
        Text(f"https://www.bilibili.com/read/cv{activity.content.id}"),
      ],
    )

  return await run_sync(make)
