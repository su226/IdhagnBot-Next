from collections.abc import Callable

from PIL import ImageOps

from idhagnbot.image import SCALE_RESAMPLE
from idhagnbot.image.card import Card, CardTab
from idhagnbot.plugins.bilibili_activity.common import fetch_image
from idhagnbot.text import escape
from idhagnbot.third_party.bilibili_activity import ExtraVideo


async def format_extra(extra: ExtraVideo) -> Callable[[Card], None]:
    cover = await fetch_image(extra.cover)

    def appender(card: Card) -> None:
        desc = f"{extra.duration} {extra.desc}"
        content = f"{escape(extra.title)}\n<span color='#888888'>{escape(desc)}</span>"
        nonlocal cover
        cover = ImageOps.contain(cover, (160, 100), SCALE_RESAMPLE)
        card.add(CardTab(content, "视频", cover))

    return appender
