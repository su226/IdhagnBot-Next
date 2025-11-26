from collections.abc import Callable

import nonebot
from anyio.to_thread import run_sync
from PIL import Image

from idhagnbot import image
from idhagnbot.asyncio import gather
from idhagnbot.image.card import Card, CardAuthor, CardText
from idhagnbot.plugins.bilibili_activity import extras
from idhagnbot.plugins.bilibili_activity.common import fetch_image
from idhagnbot.third_party.bilibili_activity import ActivityBlocked
from idhagnbot.third_party.bilibili_activity.card import CardTopic

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Segment, Text, UniMessage

CONTENT_TYPES = {
  "ARTICLE": "专栏",
  "AV": "视频",
}


async def get_appender(activity: ActivityBlocked[object]) -> Callable[[Card], None]:
  avatar, append_extra = await gather(
    fetch_image(activity.avatar),
    extras.format(activity.extra),
  )

  def appender(card: Card) -> None:
    block = Card()
    block.add(CardAuthor(avatar, activity.name))
    block.add(CardTopic(activity.topic))
    block.add(CardText(activity.content.message))
    append_extra(block, False)
    card.add(block)

  return appender


async def format(activity: ActivityBlocked[object], can_ignore: bool) -> UniMessage[Segment]:
  appender = await get_appender(activity)

  def make() -> UniMessage[Segment]:
    card = Card(0)
    appender(card)
    im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
    card.render(im, 0, 0)
    content_type = CONTENT_TYPES.get(activity.type, "动态")
    return UniMessage(
      [
        Text(f"{activity.name} 发布了充电{content_type}"),
        Text.br(),
        image.to_segment(im),
        Text.br(),
        Text(f"https://t.bilibili.com/{activity.id}"),
      ],
    )

  return await run_sync(make)
