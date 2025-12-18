from collections.abc import Callable
from time import localtime, strftime

from idhagnbot import text
from idhagnbot.image.card import Card, CardTab
from idhagnbot.third_party.bilibili_activity import ExtraVote


async def format_extra(extra: ExtraVote) -> Callable[[Card], None]:
  def appender(card: Card) -> None:
    end_time = strftime("%m-%d %H:%M", localtime(extra.end))
    content = (
      f"{text.escape(extra.title)}\n"
      f"<span color='#888888'>{extra.count}人已投票 {end_time}截止</span>"
    )
    card.add(CardTab(content, "投票"))

  return appender
