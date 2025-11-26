import re

import nonebot
from nonebot.adapters.onebot.v11 import Adapter, FriendRecallNoticeEvent, GroupRecallNoticeEvent
from nonebot.message import event_preprocessor

from idhagnbot.context import SceneIdRaw
from idhagnbot.plugins.repeat.common import (
  CONDITION_REGISTRY,
  LastMessage,
  last_messages,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Emoji, Segment, Text, UniMessage

SUPER_EMOTE_RE = re.compile(r"^/[A-Za-z0-9\u4e00-\u9fa5]+$")


async def handle_recall(
  _: GroupRecallNoticeEvent | FriendRecallNoticeEvent,
  scene_id: SceneIdRaw,
) -> None:
  if last := last_messages.get(scene_id):
    last = LastMessage(
      message=last.message,
      received_count=max(last.received_count - 1, 0),
      sending_count=last.sending_count,
      sent_count=last.sent_count,
    )


def condition(message: UniMessage[Segment]) -> bool:
  # 针对 Lagrange.OneBot 收到超级表情时有 text 消息段的缓解方案
  return not (
    len(message) == 2
    and isinstance(message[0], Emoji)
    and isinstance(text := message[1], Text)
    and SUPER_EMOTE_RE.match(text.text)
  )


def register() -> None:
  event_preprocessor(handle_recall)
  name = Adapter.get_name()
  CONDITION_REGISTRY[name] = condition
