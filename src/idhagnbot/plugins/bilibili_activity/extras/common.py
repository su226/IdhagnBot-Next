from collections.abc import Callable

from PIL import ImageOps

from idhagnbot import image, text
from idhagnbot.image.card import Card, CardTab
from idhagnbot.plugins.bilibili_activity.common import fetch_image
from idhagnbot.third_party.bilibili_activity import ExtraCommon


async def format_extra(extra: ExtraCommon) -> Callable[[Card], None]:
  cover = await fetch_image(extra.cover)

  def appender(card: Card) -> None:
    desc = f"{extra.desc1} {extra.desc2}"
    content = f"{text.escape(extra.title)}\n<span color='#888888'>{text.escape(desc)}</span>"
    nonlocal cover
    cover = ImageOps.contain(cover, (100, 100), image.get_scale_resample())
    card.add(CardTab(content, extra.head_text, cover))

  return appender
