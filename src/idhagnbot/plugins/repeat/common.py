from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

import nonebot
from nonebot.adapters import Bot, Event

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, UniMessage


@dataclass(frozen=True)
class LastMessage:
  message: UniMessage[Segment]
  received_count: int
  sending_count: int
  sent_count: int


last_messages = dict[str, LastMessage]()
COMPARATOR_REGISTRY = dict[str, Callable[[UniMessage[Segment], UniMessage[Segment]], bool]]()
CONDITION_REGISTRY = dict[str, Callable[[UniMessage[Segment]], bool]]()
HANDLER_REGISTRY = dict[
  str,
  Callable[[Bot, list[Event], UniMessage[Segment], str], Awaitable[None]],
]()
already_counted = ContextVar("already_counted", default=False)


def is_same(adapter: str, a: UniMessage[Segment], b: UniMessage[Segment]) -> bool:
  if comparator := COMPARATOR_REGISTRY.get(adapter):
    return comparator(a, b)
  return a == b


@contextmanager
def count_send(adapter: str, scene_id: str, message: UniMessage[Segment]) -> Iterator[None]:
  if (last := last_messages.get(scene_id)) and is_same(adapter, message, last.message):
    last_messages[scene_id] = LastMessage(
      message=message,
      received_count=last.received_count,
      sending_count=last.sending_count + 1,
      sent_count=last.sent_count,
    )
  token = already_counted.set(True)
  try:
    yield
  except:
    if (last := last_messages.get(scene_id)) and is_same(adapter, message, last.message):
      last_messages[scene_id] = LastMessage(
        message=message,
        received_count=last.received_count,
        sending_count=max(last.sending_count - 1, 0),
        sent_count=last.sent_count,
      )
    raise
  else:
    if (last := last_messages.get(scene_id)) and is_same(adapter, message, last.message):
      last_messages[scene_id] = LastMessage(
        message=message,
        received_count=last.received_count,
        sending_count=max(last.sending_count - 1, 0),
        sent_count=last.sent_count + 1,
      )
    else:
      last_messages[scene_id] = LastMessage(
        message=message,
        received_count=0,
        sending_count=0,
        sent_count=1,
      )
  finally:
    already_counted.reset(token)
