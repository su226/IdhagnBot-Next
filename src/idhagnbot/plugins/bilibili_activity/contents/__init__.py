# 从B站JS里复制的枚举（数字编号只在过时API中出现）
# 动态有无图片是不同的，为了区分，这里称有图动态为“相簿”，无图动态为“动态”
# 1:    DYNAMIC_TYPE_FORWARD         # 转发（内容由orig_type决定）
# 2:    DYNAMIC_TYPE_DRAW            # 有图动态（相簿）
# 4:    DYNAMIC_TYPE_WORD            # 文字动态
# 8:    DYNAMIC_TYPE_AV              # 视频
# 64:   DYNAMIC_TYPE_ARTICLE         # 专栏
# 256:  DYNAMIC_TYPE_MUSIC           # 音频
# 512, 4097, 4098, 4099, 4100, 4101:
#       DYNAMIC_TYPE_PGC             # 番剧（仅转发）
# 1024: DYNAMIC_TYPE_NONE
# 2048: DYNAMIC_TYPE_COMMON_SQUARE   # 番剧评分、活动网页等
# 2049: DYNAMIC_TYPE_COMMON_VERTICAL
# 4200: DYNAMIC_TYPE_LIVE            # 直播（仅转发）
# 4300: DYNAMIC_TYPE_MEDIALIST       # 合集（仅转发）
#       DYNAMIC_TYPE_COURSES
# 4302: DYNAMIC_TYPE_COURSES_SEASON  # 课程（仅转发）
#       DYNAMIC_TYPE_COURSES_BATCH
#       DYNAMIC_TYPE_AD
#       DYNAMIC_TYPE_BANNER
# 4305: DYNAMIC_TYPE_APPLET
# 4308: DYNAMIC_TYPE_LIVE_RCMD
# 4310: DYNAMIC_TYPE_UGC_SEASON
#       DYNAMIC_TYPE_SUBSCRIPTION
# 4311: DYNAMIC_TYPE_SUBSCRIPTION_NEW

from collections.abc import Awaitable
from typing import Any, Callable, TypeVar

import nonebot

from idhagnbot.plugins.bilibili_activity.common import IgnoredException
from idhagnbot.plugins.bilibili_activity.contents import (
  article,
  audio,
  blocked,
  common,
  forward,
  image,
  text,
  video,
)
from idhagnbot.third_party.bilibili_activity import (
  Activity,
  ContentArticle,
  ContentAudio,
  ContentBlocked,
  ContentCommon,
  ContentForward,
  ContentImage,
  ContentLiveRcmd,
  ContentText,
  ContentVideo,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Segment, Text, UniMessage


async def format_unknown(activity: Activity[object, object]) -> UniMessage[Segment]:
  return UniMessage(
    Text(
      f"{activity.name} 发布了动态\n"
      f"IdhagnBot 暂不支持解析此类动态（{activity.type}）\n"
      f"https://t.bilibili.com/{activity.id}"
    )
  )


async def ignore(activity: Activity[object, object], can_ignore: bool) -> UniMessage[Segment]:
  if can_ignore:
    raise IgnoredException(activity.type)
  return await format_unknown(activity)


TContent = TypeVar("TContent")
Formatter = tuple[
  type[TContent],
  Callable[[Activity[TContent, object], bool], Awaitable[UniMessage[Segment]]],
]
FORMATTERS: list[Formatter[Any]] = [
  (ContentText, text.format),
  (ContentImage, image.format),
  (ContentVideo, video.format),
  (ContentArticle, article.format),
  (ContentAudio, audio.format),
  (ContentCommon, common.format),
  (ContentForward, forward.format),
  (ContentLiveRcmd, ignore),
  (ContentBlocked, blocked.format),
]


async def format(
  activity: Activity[object, object],
  can_ignore: bool = True,
) -> UniMessage[Segment]:
  for type, formatter in FORMATTERS:
    if isinstance(activity.content, type):
      return await formatter(activity, can_ignore)
  return await format_unknown(activity)
