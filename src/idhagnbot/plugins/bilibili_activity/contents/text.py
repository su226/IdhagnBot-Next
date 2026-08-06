import asyncio
from collections.abc import Callable

from arclet.entari import MessageChain, Text
from PIL import Image
from satori.element import Br

from idhagnbot.image import to_segment
from idhagnbot.image.card import Card, CardAuthor
from idhagnbot.plugins.bilibili_activity.common import check_ignore, fetch_image
from idhagnbot.plugins.bilibili_activity.extras import format_extra
from idhagnbot.third_party.bilibili_activity import ActivityText
from idhagnbot.third_party.bilibili_activity.card import (
    CardRichText,
    CardTopic,
    fetch_emojis,
)


async def get_appender(activity: ActivityText[object]) -> Callable[[Card], None]:
    avatar, emotions, append_extra = await asyncio.gather(
        fetch_image(activity.avatar),
        fetch_emojis(activity.content.richtext),
        format_extra(activity.extra),
    )

    def appender(card: Card) -> None:
        block = Card()
        block.add(CardAuthor(avatar, activity.name))
        lines = 3 if activity.extra else 6
        block.add(CardTopic(activity.topic))
        block.add(CardRichText(activity.content.richtext, emotions, 32, lines))
        append_extra(block, block=False)
        card.add(block)

    return appender


async def format_activity(
    activity: ActivityText[object],
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
