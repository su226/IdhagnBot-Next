import asyncio
from typing import Callable

import nonebot
from PIL import Image

from idhagnbot import image
from idhagnbot.image.card import Card, CardAuthor, CardCover, CardText
from idhagnbot.plugins.bilibili_activity import extras
from idhagnbot.plugins.bilibili_activity.common import fetch_image
from idhagnbot.third_party.bilibili_activity import ActivityAudio
from idhagnbot.third_party.bilibili_activity.card import CardTopic

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Segment, Text, UniMessage


async def get_appender(activity: ActivityAudio[object]) -> Callable[[Card], None]:
  avatar, cover, append_extra = await asyncio.gather(
    fetch_image(activity.avatar),
    fetch_image(activity.content.cover),
    extras.format(activity.extra),
  )

  def appender(card: Card) -> None:
    block = Card()
    block.add(CardAuthor(avatar, activity.name))
    block.add(CardTopic(activity.topic))
    block.add(CardText(activity.content.title, size=40, lines=2))
    block.add(CardText(activity.content.label, size=32, lines=1))
    card.add(block)
    card.add(CardCover(cover))
    if activity.content.desc and activity.content.desc != "-":
      block = Card()
      block.add(CardText(activity.content.desc, size=32, lines=3))
      append_extra(block, False)
      card.add(block)
    else:
      append_extra(card, True)

  return appender


async def format(activity: ActivityAudio[object], can_ignore: bool) -> UniMessage[Segment]:
  appender = await get_appender(activity)

  def make() -> UniMessage[Segment]:
    card = Card(0)
    appender(card)
    im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
    card.render(im, 0, 0)
    return UniMessage(
      [
        Text(f"{activity.name} 发布了音频"),
        Text.br(),
        image.to_segment(im),
        Text.br(),
        Text(f"https://www.bilibili.com/audio/au{activity.content.id}"),
      ],
    )

  return await asyncio.to_thread(make)
