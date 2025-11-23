from typing import Callable

import nonebot
from anyio.to_thread import run_sync
from PIL import Image

from idhagnbot import image
from idhagnbot.asyncio import gather
from idhagnbot.image.card import Card, CardAuthor
from idhagnbot.plugins.bilibili_activity import extras
from idhagnbot.plugins.bilibili_activity.common import check_ignore, fetch_image
from idhagnbot.third_party.bilibili_activity import ActivityText
from idhagnbot.third_party.bilibili_activity.card import CardRichText, CardTopic, fetch_emotions

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Segment, Text, UniMessage


async def get_appender(activity: ActivityText[object]) -> Callable[[Card], None]:
  avatar, emotions, append_extra = await gather(
    fetch_image(activity.avatar),
    fetch_emotions(activity.content.richtext),
    extras.format(activity.extra),
  )

  def appender(card: Card) -> None:
    block = Card()
    block.add(CardAuthor(avatar, activity.name))
    lines = 3 if activity.extra else 6
    block.add(CardTopic(activity.topic))
    block.add(CardRichText(activity.content.richtext, emotions, 32, lines))
    append_extra(block, False)
    card.add(block)

  return appender


async def format(activity: ActivityText[object], can_ignore: bool) -> UniMessage[Segment]:
  if can_ignore:
    check_ignore(activity.content.text)
  appender = await get_appender(activity)

  def make() -> UniMessage[Segment]:
    card = Card(0)
    appender(card)
    im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
    card.render(im, 0, 0)
    return UniMessage(
      [
        Text(f"{activity.name} 发布了动态"),
        Text.br(),
        image.to_segment(im),
        Text.br(),
        Text(f"https://t.bilibili.com/{activity.id}"),
      ],
    )

  return await run_sync(make)
