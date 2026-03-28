import random
import re
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import cached_property
from typing import Any, ClassVar

import nonebot
from nonebot.adapters import Bot, Event
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.config import SharedConfig

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("idhagnbot.plugins.chat_record")
from nonebot_plugin_alconna import Segment, UniMessage
from nonebot_plugin_orm import Model, get_session

from idhagnbot.plugins.chat_record import Message


class Config(BaseModel):
  repeat_every: int = 2
  max_repeat: int = 1
  global_ignore: list[re.Pattern[str]] = Field(default_factory=list)
  local_ignore: dict[str, list[re.Pattern[str]]] = Field(default_factory=dict)


class LastMessage(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_repeat_last_message"
  scene_id: Mapped[str] = mapped_column(primary_key=True)
  run_id: Mapped[int]
  message: Mapped[str]
  received_count: Mapped[int]
  sending_count: Mapped[int]
  sent_count: Mapped[int]

  @cached_property
  def unimessage(self) -> UniMessage[Segment]:
    return UniMessage.load(self.message)


Comparator = Callable[[UniMessage[Segment], UniMessage[Segment]], bool]
Condition = Callable[[UniMessage[Segment]], bool]
Handler = Callable[[Bot, list[Event], UniMessage[Segment], str], Awaitable[None]]
CONFIG = SharedConfig("repeat", Config)
RUN_ID = random.randrange(-0x80000000, 0x80000000)
COMPARATOR_REGISTRY = dict[str, Comparator]()
CONDITION_REGISTRY = dict[str, Condition]()
HANDLER_REGISTRY = dict[str, Handler]()
ALREADY_COUNTED = ContextVar("ALREADY_COUNTED", default=False)


def is_same(adapter: str, received: UniMessage[Segment], recorded: LastMessage) -> bool:
  if recorded.run_id != RUN_ID:
    return False
  if comparator := COMPARATOR_REGISTRY.get(adapter):
    return comparator(received, recorded.unimessage)
  return received == recorded.unimessage


async def count_received(adapter: str, scene_id: str, message: UniMessage[Segment]) -> None:
  async with get_session() as sql:
    last = await sql.get(LastMessage, scene_id)
    if last:
      if is_same(adapter, message, last):
        last.received_count += 1
      else:
        last.message = message.dump(media_save_dir=False, json=True)
        last.run_id = RUN_ID
        last.received_count = 1
        last.sending_count = 0
        last.sent_count = 0
    else:
      last = LastMessage(
        scene_id=scene_id,
        message=message.dump(media_save_dir=False, json=True),
        run_id=RUN_ID,
        received_count=1,
        sending_count=0,
        sent_count=0,
      )
    sql.add(last)
    await sql.commit()


async def count_sending(adapter: str, scene_id: str, message: UniMessage[Segment]) -> None:
  async with get_session() as sql:
    last = await sql.get(LastMessage, scene_id)
    if last and is_same(adapter, message, last):
      last.sending_count += 1
      sql.add(last)
      await sql.commit()


async def count_sent(adapter: str, scene_id: str, message: UniMessage[Segment]) -> None:
  async with get_session() as sql:
    last = await sql.get(LastMessage, scene_id)
    if last:
      if is_same(adapter, message, last):
        last.sent_count += 1
        last.sending_count = max(last.sending_count - 1, 0)
      else:
        last.message = message.dump(media_save_dir=False, json=True)
        last.run_id = RUN_ID
        last.received_count = 0
        last.sending_count = 0
        last.sent_count = 1
    else:
      last = LastMessage(
        scene_id=scene_id,
        message=message.dump(media_save_dir=False, json=True),
        run_id=RUN_ID,
        received_count=0,
        sending_count=0,
        sent_count=1,
      )
    sql.add(last)
    await sql.commit()


async def count_send_failed(adapter: str, scene_id: str, message: UniMessage[Segment]) -> None:
  async with get_session() as sql:
    last = await sql.get(LastMessage, scene_id)
    if last and is_same(adapter, message, last):
      last.sending_count = max(last.sending_count - 1, 0)
      sql.add(last)
      await sql.commit()


async def count_recall(adapter: str, scene_id: str, message_id: str) -> None:
  async with get_session() as sql:
    last = await sql.get(LastMessage, scene_id)
    message = await sql.execute(
      select(Message)
      .where(Message.scene_id == scene_id, Message.message_id == message_id)
      .order_by(desc(Message.record_id))
      .limit(1),
    )
    message = message.first()
    if message and last and is_same(adapter, message[0].unimessage, last):
      if message[0].outgoing:
        last.sent_count = max(last.sent_count - 1, 0)
      else:
        last.received_count = max(last.received_count - 1, 0)
      sql.add(last)
      await sql.commit()


@asynccontextmanager
async def count_send(
  adapter: str,
  scene_id: str,
  message: UniMessage[Segment],
) -> AsyncGenerator[None, None]:
  await count_sending(adapter, scene_id, message)
  token = ALREADY_COUNTED.set(True)
  try:
    yield
  except:
    await count_send_failed(adapter, scene_id, message)
    raise
  else:
    await count_sent(adapter, scene_id, message)
  finally:
    ALREADY_COUNTED.reset(token)
