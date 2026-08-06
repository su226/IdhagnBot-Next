from collections.abc import Callable

from idhagnbot.image.card import Card, CardTab
from idhagnbot.text import escape
from idhagnbot.third_party.bilibili_activity import ExtraReserve


async def format_extra(extra: ExtraReserve) -> Callable[[Card], None]:
    def appender(card: Card) -> None:
        title = "预约"
        if extra.status != "reserving":
            title += "（已结束）"
        desc = extra.desc
        if extra.status == ("streaming" if extra.type == "live" else "expired"):
            desc += f" {extra.desc2}"
        content = (
            f"{escape(extra.title)}\n"
            f"<span color='#888888'>{escape(desc)} {extra.count}人预约</span>"
        )
        if extra.link_text:
            content += f"\n<span color='#00aeec'>{escape(extra.link_text)}</span>"
        card.add(CardTab(content, title))

    return appender
