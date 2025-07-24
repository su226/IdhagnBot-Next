from typing import Callable

from idhagnbot import text
from idhagnbot.image.card import Card, CardTab
from idhagnbot.third_party.bilibili_activity import ExtraReserve


async def format(extra: ExtraReserve) -> Callable[[Card], None]:
  def appender(card: Card) -> None:
    title = "预约"
    if extra.status != "reserving":
      title += "（已结束）"
    desc = extra.desc
    if extra.status == ("streaming" if extra.type == "live" else "expired"):
      desc += f" {extra.desc2}"
    content = (
      f"{text.escape(extra.title)}\n"
      f"<span color='#888888'>{text.escape(desc)} {extra.count}人预约</span>"
    )
    if extra.link_text:
      content += f"\n<span color='#00aeec'>{text.escape(extra.link_text)}</span>"
    card.add(CardTab(content, title))
  return appender
