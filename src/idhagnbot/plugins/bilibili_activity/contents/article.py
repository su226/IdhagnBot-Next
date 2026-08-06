import asyncio
from collections.abc import Callable

from arclet.entari import MessageChain, Text
from PIL import Image, ImageOps
from satori.element import Br

from idhagnbot.image import SCALE_RESAMPLE, to_segment
from idhagnbot.image.card import Card, CardAuthor, CardCover, CardText
from idhagnbot.plugins.bilibili_activity.common import (
    IMAGE_GAP,
    fetch_image,
    fetch_images,
)
from idhagnbot.plugins.bilibili_activity.extras import format_extra
from idhagnbot.third_party.bilibili_activity import ActivityArticle
from idhagnbot.third_party.bilibili_activity.card import CardTopic


async def get_appender(activity: ActivityArticle[object]) -> Callable[[Card], None]:
    avatar, covers, append_extra = await asyncio.gather(
        fetch_image(activity.avatar),
        fetch_images(*activity.content.covers),
        format_extra(activity.extra),
    )

    def appender(card: Card) -> None:
        nonlocal covers
        if len(covers) == 1:
            cover = covers[0]
        else:
            gaps = len(covers) - 1
            size = 640 - gaps * IMAGE_GAP
            covers = [
                ImageOps.fit(cover, (size, size), SCALE_RESAMPLE) for cover in covers
            ]
            cover = Image.new("RGB", (640, size), (255, 255, 255))
            for i, v in enumerate(covers):
                cover.paste(v, (i * (size + IMAGE_GAP), 0))
        block = Card()
        block.add(CardAuthor(avatar, activity.name))
        block.add(CardTopic(activity.topic))
        block.add(CardText(activity.content.title, size=40, lines=2))
        card.add(block)
        card.add(CardCover(cover, crop=False))
        block = Card()
        block.add(CardText(activity.content.desc, size=32, lines=3))
        append_extra(block, block=False)
        card.add(block)

    return appender


async def format_activity(
    activity: ActivityArticle[object],
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
                Text(f"{activity.name} 发布了专栏"),
                Br(),
                to_segment(im),
                Br(),
                Text(f"https://www.bilibili.com/read/cv{activity.content.id}"),
            ],
        )

    return await asyncio.to_thread(make)
