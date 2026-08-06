import asyncio
from collections.abc import Callable

from arclet.entari import MessageChain, Text
from PIL import Image, ImageOps
from satori.element import Br

from idhagnbot.image import SCALE_RESAMPLE, to_segment
from idhagnbot.image.card import Card, CardAuthor, CardMargin, CardTab
from idhagnbot.plugins.bilibili_activity.common import check_ignore, fetch_image
from idhagnbot.plugins.bilibili_activity.extras import format_extra
from idhagnbot.text import escape
from idhagnbot.third_party.bilibili_activity import ActivityCommon
from idhagnbot.third_party.bilibili_activity.card import (
    CardRichText,
    CardTopic,
    fetch_emojis,
)


async def get_appender(activity: ActivityCommon[object]) -> Callable[[Card], None]:
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
        block.add(CardRichText(activity.content.richtext, emotions, 32, 6))
        block.add(CardMargin())
        content = (
            f"{escape(activity.content.title)}\n"
            f"<span color='#888888'>{escape(activity.content.desc)}</span>"
        )
        nonlocal cover
        cover = ImageOps.fit(cover, (100, 100), SCALE_RESAMPLE)
        block.add(CardTab(content, activity.content.badge, cover))
        append_extra(block, block=False)
        card.add(block)

    return appender


async def format_activity(
    activity: ActivityCommon[object],
    can_ignore: bool,
) -> MessageChain:
    if can_ignore:
        check_ignore(activity.content.text)
    appender = await get_appender(activity)

    def make() -> MessageChain:
        card = Card(0)
        appender(card)
        im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
        card.render(im, 0, 0)
        return MessageChain(
            [
                Text(f"{activity.name} 发布了动态"),
                Br(),
                to_segment(im),
                Br(),
                Text(f"https://t.bilibili.com/{activity.id}"),
            ],
        )

    return await asyncio.to_thread(make)
