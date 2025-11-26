# ADDITIONAL_TYPE_PGC
# ADDITIONAL_TYPE_GOODS
# ADDITIONAL_TYPE_VOTE    # 投票
# ADDITIONAL_TYPE_COMMON
# ADDITIONAL_TYPE_MATCH
# ADDITIONAL_TYPE_UP_RCMD
# ADDITIONAL_TYPE_UGC     # 视频
# ADDITIONAL_TYPE_RESERVE # 直播预约

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

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
  (ExtraVote, vote.format),
  (ExtraVideo, video.format),
  (ExtraReserve, reserve.format),
  (ExtraGoods, goods.format),
  (ExtraCommon, common.format),
]


def format_noop(card: Card, block: bool = False) -> None:
  pass


def get_unknown_appender(type: str) -> Callable[[Card], None]:
  def appender(card: Card) -> None:
    card.add(CardTab(f"IdhagnBot 暂不支持解析此内容（{type}）", "额外内容"))

  return appender


async def format(extra: Extra[object] | None) -> Callable[[Card, bool], None]:
  if extra is None:
    return format_noop
  for type, get_appender in FORMATTERS:
    if isinstance(extra.value, type):
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
