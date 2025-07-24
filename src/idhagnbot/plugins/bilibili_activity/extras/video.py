from typing import Callable

from PIL import ImageOps

from idhagnbot import image, text
from idhagnbot.image.card import Card, CardTab
from idhagnbot.plugins.bilibili_activity.common import fetch_image
from idhagnbot.third_party.bilibili_activity import ExtraVideo


async def format(extra: ExtraVideo) -> Callable[[Card], None]:
  cover = await fetch_image(extra.cover)

  def appender(card: Card) -> None:
    desc = f"{extra.duration} {extra.desc}"
    content = (
      f"{text.escape(extra.title)}\n"
      f"<span color='#888888'>{text.escape(desc)}</span>"
    )
    nonlocal cover
    cover = ImageOps.contain(cover, (160, 100), image.get_scale_resample())
    card.add(CardTab(content, "视频", cover))
  return appender
