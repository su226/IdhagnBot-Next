import re

import nonebot
from nonebot.adapters.onebot.v11 import Adapter, FriendRecallNoticeEvent, GroupRecallNoticeEvent
from nonebot.message import event_preprocessor
from yarl import URL

from idhagnbot.context import SceneIdRaw
from idhagnbot.plugins.repeat.common import (
  COMPARATOR_REGISTRY,
  CONDITION_REGISTRY,
  LastMessage,
  last_messages,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Emoji, Image, Segment, Text, UniMessage

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


def _extract_image_id(image_id: str | None) -> str | None:
  if not image_id:
    return None
  # Lagrange.OneBot 的 file 是链接不是文件名
  if image_id.startswith(("http://", "https://")):
    url = URL(image_id)
    if url.host == "gchat.qpic.cn" and url.path.startswith("/gchatpic_new"):
      return url.parts[3].split("-", 2)[2]
    if url.host == "multimedia.nt.qq.com.cn" and url.path.startswith("/download"):
      return url.query["fileid"]
    return None
  # 有时候会出现MD5相同但是拓展名/大小写/间隔符不同的情况，所以标准化
  return image_id.rsplit(".", 1)[0].casefold().replace("-", "").replace("_", "")


def _image_equal(a: Image, b: Image) -> bool:
  id_a = _extract_image_id(a.id)
  id_b = _extract_image_id(b.id)
  return id_a == id_b if id_a and id_b else a == b


def comparator(a: UniMessage[Segment], b: UniMessage[Segment]) -> bool:
  if len(a) != len(b):
    return False
  for seg1, seg2 in zip(a, b, strict=True):
    if isinstance(seg1, Image) and isinstance(seg2, Image):
      if not _image_equal(seg1, seg2):
        return False
    elif seg1 != seg2:
      return False
  return True


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
  COMPARATOR_REGISTRY[name] = comparator
