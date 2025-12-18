# ADDITIONAL_TYPE_PGC
# ADDITIONAL_TYPE_GOODS
# ADDITIONAL_TYPE_VOTE    # 投票
# ADDITIONAL_TYPE_COMMON
# ADDITIONAL_TYPE_MATCH
# ADDITIONAL_TYPE_UP_RCMD
# ADDITIONAL_TYPE_UGC     # 视频
# ADDITIONAL_TYPE_RESERVE # 直播预约

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from idhagnbot.image.card import Card, CardMargin, CardTab
from idhagnbot.plugins.bilibili_activity.extras import common, goods, reserve, video, vote
from idhagnbot.third_party.bilibili_activity import (
  Extra,
  ExtraCommon,
  ExtraGoods,
  ExtraReserve,
  ExtraVideo,
  ExtraVote,
)

TExtra = TypeVar("TExtra")
Formatter = tuple[type[TExtra], Callable[[TExtra], Awaitable[Callable[[Card], None]]]]
FORMATTERS: list[Formatter[Any]] = [
  (ExtraVote, vote.format_extra),
  (ExtraVideo, video.format_extra),
  (ExtraReserve, reserve.format_extra),
  (ExtraGoods, goods.format_extra),
  (ExtraCommon, common.format_extra),
]


def format_noop(card: Card, block: bool = False) -> None:
  pass


def get_unknown_appender(activity_type: str) -> Callable[[Card], None]:
  def appender(card: Card) -> None:
    card.add(CardTab(f"IdhagnBot 暂不支持解析此内容（{activity_type}）", "额外内容"))

  return appender


class ExtraAppender(Protocol):
  def __call__(self, card: Card, block: bool) -> None: ...


async def format_extra(extra: Extra[object] | None) -> ExtraAppender:
  if extra is None:
    return format_noop
  for activity_type, get_appender in FORMATTERS:
    if isinstance(extra.value, activity_type):
      appender = await get_appender(extra.value)
      break
  else:
    appender = get_unknown_appender(extra.type)

  def do_format(card: Card, block: bool = False) -> None:
    if block:
      content = Card()
      appender(content)
      card.add(content)
    else:
      card.add(CardMargin())
      appender(card)

  return do_format
