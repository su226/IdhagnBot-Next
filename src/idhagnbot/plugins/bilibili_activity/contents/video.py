import asyncio
from collections.abc import Callable

from arclet.entari import MessageChain, Text
from PIL import Image
from satori.element import Br

from idhagnbot.image import to_segment
from idhagnbot.image.card import Card, CardAuthor, CardCover, CardText
from idhagnbot.plugins.bilibili_activity.common import fetch_image
from idhagnbot.plugins.bilibili_activity.extras import format_extra
from idhagnbot.third_party.bilibili_activity import ActivityVideo
from idhagnbot.third_party.bilibili_activity.card import (
    CardRichText,
    CardTopic,
    fetch_emojis,
)


async def get_appender(activity: ActivityVideo[object]) -> Callable[[Card], None]:
    avatar, cover, emotions, append_extra = await asyncio.gather(
        fetch_image(activity.avatar),
        fetch_image(activity.content.cover),
        fetch_emojis(activity.content.richtext),
        format_extra(activity.extra),
    )

    def appender(card: Card) -> None:
        block = Card()
        block.add(CardAuthor(avatar, activity.name))
        block.add(CardTopic(activity.topic))
        if activity.content.richtext:
            block.add(CardRichText(activity.content.richtext, emotions, 32, 3))
        if activity.content.title:  # 动态视频没有标题
            block.add(CardText(activity.content.title, size=40, lines=2))
        card.add(block)
        card.add(CardCover(cover))
        if activity.content.desc and activity.content.desc != "-":
            block = Card()
            block.add(CardText(activity.content.desc, size=32, lines=3))
            append_extra(block, block=False)
            card.add(block)
        else:
            append_extra(card, block=True)

    return appender


async def format_activity(
    activity: ActivityVideo[object],
    can_ignore: bool,
) -> MessageChain:
    appender = await get_appender(activity)

    def make() -> MessageChain:
        card = Card(0)
        appender(card)
        im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
        card.render(im, 0, 0)
        return MessageChain(
            [
                Text(f"{activity.name} 发布了视频"),
                Br(),
                to_segment(im),
                Br(),
                Text(f"https://www.bilibili.com/video/{activity.content.bvid}"),
            ],
        )

    return await asyncio.to_thread(make)
