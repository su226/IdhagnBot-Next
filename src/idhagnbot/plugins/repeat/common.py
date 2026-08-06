import random
import re
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import cached_property

from arclet.entari import MessageChain, MessageCreatedEvent, metadata, plugin_config
from arclet.entari.filter.parse import parse_filter
from entari_plugin_database import Base, get_session  # entari: plugin
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.orm import Mapped, mapped_column


class Config(BaseModel):
    repeat_every: int = 2
    max_repeat: int = 1
    filter: str = "True"
    ignore: dict[str, list[re.Pattern[str]]] = Field(default_factory=dict)


class LastMessage(Base):
    __tablename__ = "idhagnbot_repeat_last_message"
    platform: Mapped[str] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[int]
    message: Mapped[str]
    received_count: Mapped[int]
    sending_count: Mapped[int]
    sent_count: Mapped[int]

    @cached_property
    def chain(self) -> MessageChain:
        return MessageChain.of(self.message)


type Comparator = Callable[[MessageChain, MessageChain], bool]
type Condition = Callable[[MessageChain], bool]
type Handler = Callable[[MessageCreatedEvent], Awaitable[None]]
metadata("", config=Config)
CONFIG = plugin_config(Config)
FILTER = parse_filter(CONFIG.filter)
RUN_ID = random.randrange(-0x80000000, 0x80000000)
COMPARATOR_REGISTRY = dict[str, Comparator]()
CONDITION_REGISTRY = dict[str, Condition]()
HANDLER_REGISTRY = dict[str, Handler]()
ALREADY_COUNTED = ContextVar("ALREADY_COUNTED", default=False)


def is_same(adapter: str, received: MessageChain, recorded: LastMessage) -> bool:
    if recorded.run_id != RUN_ID:
        return False
    if comparator := COMPARATOR_REGISTRY.get(adapter):
        return comparator(received, recorded.chain)
    return received == recorded.chain


async def count_received(
    platform: str,
    channel_id: str,
    message: MessageChain,
) -> None:
    async with get_session() as db:
        last = await db.get(LastMessage, (platform, channel_id))
        if last:
            if is_same(platform, message, last):
                last.received_count += 1
            else:
                last.message = str(message)
                last.run_id = RUN_ID
                last.received_count = 1
                last.sending_count = 0
                last.sent_count = 0
        else:
            last = LastMessage(
                platform=platform,
                channel_id=channel_id,
                message=str(message),
                run_id=RUN_ID,
                received_count=1,
                sending_count=0,
                sent_count=0,
            )
        db.add(last)
        await db.commit()


async def count_sending(
    platform: str,
    channel_id: str,
    message: MessageChain,
) -> None:
    async with get_session() as db:
        last = await db.get(LastMessage, (platform, channel_id))
        if last and is_same(platform, message, last):
            last.sending_count += 1
            db.add(last)
            await db.commit()


async def count_sent(platform: str, channel_id: str, message: MessageChain) -> None:
    async with get_session() as db:
        last = await db.get(LastMessage, (platform, channel_id))
        if last:
            if is_same(platform, message, last):
                last.sent_count += 1
                last.sending_count = max(last.sending_count - 1, 0)
            else:
                last.message = str(message)
                last.run_id = RUN_ID
                last.received_count = 0
                last.sending_count = 0
                last.sent_count = 1
        else:
            last = LastMessage(
                platform=platform,
                channel_id=channel_id,
                message=str(message),
                run_id=RUN_ID,
                received_count=0,
                sending_count=0,
                sent_count=1,
            )
        db.add(last)
        await db.commit()


async def count_send_failed(
    platform: str,
    channel_id: str,
    message: MessageChain,
) -> None:
    async with get_session() as db:
        last = await db.get(LastMessage, (platform, channel_id))
        if last and is_same(platform, message, last):
            last.sending_count = max(last.sending_count - 1, 0)
            db.add(last)
            await db.commit()


async def count_recall(platform: str, channel_id: str) -> None:
    async with get_session() as db:
        await db.execute(
            delete(LastMessage).where(
                LastMessage.platform == platform,
                LastMessage.channel_id == channel_id,
            ),
        )
        await db.commit()


@asynccontextmanager
async def count_send(
    adapter: str,
    scene_id: str,
    message: MessageChain,
) -> AsyncGenerator[None]:
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
