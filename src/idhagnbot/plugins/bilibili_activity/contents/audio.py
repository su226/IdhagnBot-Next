import asyncio
from collections.abc import Callable

from arclet.entari import MessageChain, Text
from PIL import Image
from satori.element import Br

from idhagnbot.image import to_segment
from idhagnbot.image.card import Card, CardAuthor, CardCover, CardText
from idhagnbot.plugins.bilibili_activity.common import fetch_image
from idhagnbot.plugins.bilibili_activity.extras import format_extra
from idhagnbot.third_party.bilibili_activity import ActivityAudio
from idhagnbot.third_party.bilibili_activity.card import CardTopic


async def get_appender(activity: ActivityAudio[object]) -> Callable[[Card], None]:
    avatar, cover, append_extra = await asyncio.gather(
        fetch_image(activity.avatar),
        fetch_image(activity.content.cover),
        format_extra(activity.extra),
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
            append_extra(block, block=False)
            card.add(block)
        else:
            append_extra(card, block=True)

    return appender


async def format_activity(
    activity: ActivityAudio[object],
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
                Text(f"{activity.name} 发布了音频"),
                Br(),
                to_segment(im),
                Br(),
                Text(f"https://www.bilibili.com/audio/au{activity.content.id}"),
            ],
        )

    return await asyncio.to_thread(make)
