import asyncio
import math
from typing import Callable

import nonebot
from PIL import Image, ImageOps

from idhagnbot import image
from idhagnbot.image.card import Card, CardAuthor, CardCover, CardText
from idhagnbot.plugins.bilibili_activity import extras
from idhagnbot.plugins.bilibili_activity.common import (
  IMAGE_GAP,
  check_ignore,
  fetch_image,
  fetch_images,
)
from idhagnbot.third_party.bilibili_activity import ActivityOpus
from idhagnbot.third_party.bilibili_activity.card import CardRichText, CardTopic, fetch_emotions

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Segment, Text, UniMessage


async def get_appender(activity: ActivityOpus[object]) -> Callable[[Card], None]:
  image_infos = (
    activity.content.images[:9] if len(activity.content.images) > 9 else activity.content.images
  )
  avatar, images, emotions, append_extra = await asyncio.gather(
    fetch_image(activity.avatar),
    fetch_images(*[image.src for image in image_infos]),
    fetch_emotions(activity.content.richtext),
    extras.format(activity.extra),
  )

  def appender(card: Card) -> None:
    nonlocal images
    block = Card()
    block.add(CardAuthor(avatar, activity.name))
    block.add(CardTopic(activity.topic))
    if activity.content.title:
      block.add(CardText(activity.content.title, "sans bold"))
    lines = 6 if not images and not activity.extra else 3
    block.add(CardRichText(activity.content.richtext, emotions, 32, lines))
    card.add(block)
    if len(images) == 1:
      cover = ImageOps.fit(images[0], (640, 400), image.get_resample())
      card.add(CardCover(cover, False))
    elif len(images) != 0:
      columns = 2 if len(images) in {2, 4} else 3
      rows = math.ceil(len(images) / columns)
      size = (640 - (columns - 1) * IMAGE_GAP) // columns
      height = size * rows + max(rows - 1, 0) * IMAGE_GAP
      images = [ImageOps.fit(im, (size, size), image.get_resample()) for im in images]
      cover = Image.new("RGB", (640, height), (255, 255, 255))
      for i, v in enumerate(images):
        y, x = divmod(i, columns)
        x = int(x / (columns - 1) * (640 - size))
        y = y * (size + IMAGE_GAP)
        cover.paste(v, (x, y))
      card.add(CardCover(cover, False))
    append_extra(card, True)

  return appender


async def format(activity: ActivityOpus[object], can_ignore: bool) -> UniMessage[Segment]:
  if can_ignore:
    check_ignore(activity.content.text)
  appender = await get_appender(activity)

  def make() -> UniMessage[Segment]:
    card = Card(0)
    appender(card)
    im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
    card.render(im, 0, 0)
    type = "专栏" if activity.type == "ARTICLE" else "动态"
    return UniMessage(
      [
        Text(f"{activity.name} 发布了{type}"),
        Text.br(),
        image.to_segment(im),
        Text.br(),
        Text(f"https://bilibili.com/opus/{activity.id}"),
      ],
    )

  return await asyncio.to_thread(make)
