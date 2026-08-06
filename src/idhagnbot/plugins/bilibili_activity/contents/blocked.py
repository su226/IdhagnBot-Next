import asyncio
from collections.abc import Callable

from arclet.entari import MessageChain, Text
from PIL import Image
from satori.element import Br

from idhagnbot.image import to_segment
from idhagnbot.image.card import Card, CardAuthor, CardText
from idhagnbot.plugins.bilibili_activity.common import fetch_image
from idhagnbot.plugins.bilibili_activity.extras import format_extra
from idhagnbot.third_party.bilibili_activity import ActivityBlocked
from idhagnbot.third_party.bilibili_activity.card import CardTopic

CONTENT_TYPES = {
    "ARTICLE": "专栏",
    "AV": "视频",
}


async def get_appender(activity: ActivityBlocked[object]) -> Callable[[Card], None]:
    avatar, append_extra = await asyncio.gather(
        fetch_image(activity.avatar),
        format_extra(activity.extra),
    )

    def appender(card: Card) -> None:
        block = Card()
        block.add(CardAuthor(avatar, activity.name))
        block.add(CardTopic(activity.topic))
        block.add(CardText(activity.content.message))
        append_extra(block, block=False)
        card.add(block)

    return appender


async def format_activity(
    activity: ActivityBlocked[object],
    can_ignore: bool,
) -> MessageChain:
    appender = await get_appender(activity)

    def make() -> MessageChain:
        card = Card(0)
        appender(card)
        im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
        card.render(im, 0, 0)
        content_type = CONTENT_TYPES.get(activity.type, "动态")
        return MessageChain(
            [
                Text(f"{activity.name} 发布了充电{content_type}"),
                Br(),
                to_segment(im),
                Br(),
                Text(f"https://t.bilibili.com/{activity.id}"),
            ],
        )

    return await asyncio.to_thread(make)
