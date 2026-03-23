from typing import Any, cast

from nonebot.adapters import Event
from nonebot.adapters.telegram import Adapter, Message
from nonebot.adapters.telegram.event import MessageEvent
from nonebot.adapters.telegram.message import Entity

from idhagnbot.plugins.alias.common import COMMAND_UPDATER_REGISTRY, CONFIG


def update_command(scene_id: str, event: Event) -> None:
  assert isinstance(event, MessageEvent)
  # 1. 把不连续的 Entity 拼接到一起
  text = ""
  for seg in event.message:
    if not isinstance(seg, Entity):
      break
    text += seg.data["text"]

  # 2. 移除左面的空格
  orig_len = len(text)
  text = text.lstrip()
  remove_len = orig_len - len(text)

  # 3. 获取别名
  alias = CONFIG().get_replacement(scene_id, text)
  if not alias:
    return
  remove_len += len(alias.name)

  # 4. 找到 remove_len 位置对应的 Entity 下标
  message: Message[Any] = event.message
  keep_pos = 0
  while True:
    seg: Entity = message[keep_pos]
    seg_text = cast(str, seg.data["text"])
    if len(seg_text) > remove_len:
      # 当前 Entity 的文本足够 remove_len，只删除前面的一部分
      seg.data["text"] = seg_text[remove_len:]
      break
    # 当前 Entity 的文本不够 remove_len，延迟删除整段
    keep_pos += 1
    remove_len -= len(seg_text)
    if keep_pos >= len(message):
      break

  # 5. 延迟删除所有需要删除的段，并插入别名替换后的段
  if keep_pos == 0:
    message.insert(0, Entity.text(alias.definition))
  else:
    del message[: keep_pos - 1]
    message[0] = Entity.text(alias.definition)


def register() -> None:
  COMMAND_UPDATER_REGISTRY[Adapter.get_name()] = update_command
