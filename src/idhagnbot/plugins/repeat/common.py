import random
import re
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable, Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import cached_property

from arclet.entari import MessageChain, MessageCreatedEvent, metadata, plugin_config
from entari_plugin_database import Base, get_session  # entari: plugin
from pydantic import BaseModel, Field
from satori import Element, Text
from sqlalchemy import delete
from sqlalchemy.orm import Mapped, mapped_column


class OverridableConfigPartial(BaseModel):
    every: int | None = None
    """每几条消息复读一条"""

    max: int | None = None
    """最多复读几条，设置为 0 以禁用复读"""

    chance: float | None = None
    """满足条件时每条消息有多少概率复读一次"""

    special: str | None = None
    """特殊消息的内容"""

    special_chance: float | None = None
    """复读时有多大概率触发特殊消息"""


class OverridableConfig(BaseModel):
    every: int = 2
    """每几条消息复读一条"""

    max: int = 1
    """最多复读几条，设置为 0 以禁用复读"""

    chance: float = 0.3333
    """满足条件时每条消息有多少概率复读一次"""

    special: str = "打断复读"
    """特殊消息的内容"""

    special_chance: float = 0.01
    """复读时有多大概率触发特殊消息，设置为 0 以禁用"""

    def merge(self, config: OverridableConfig | OverridableConfigPartial) -> None:
        if config.every is not None:
            self.every = config.every
        if config.max is not None:
            self.max = config.max
        if config.chance is not None:
            self.chance = config.chance
        if config.special is not None:
            self.special = config.special
        if config.special_chance is not None:
            self.special_chance = config.special_chance


class ExtendableConfig(BaseModel):
    blacklist: list[re.Pattern[str]] = Field(default_factory=list)
    """黑名单正则"""


class ConfigPartial(OverridableConfigPartial, ExtendableConfig):
    pass


def match_blacklist(
    blacklist: list[re.Pattern[str]],
    message: Iterable[Element],
) -> bool:
    for element in message:
        if isinstance(element, Text):
            for pattern in blacklist:
                if pattern.search(element.text):
                    return True
        elif match_blacklist(blacklist, element.children):
            return True
    return False


class Config(OverridableConfig, ExtendableConfig):
    scene_config: dict[str, ConfigPartial] = Field(default_factory=dict)
    """按场景设置，场景名可以是：<平台>、<平台>:<群组>、<平台>:<频道>，设置将会继承。"""

    def get_overridable_config_in(
        self,
        platform: str,
        guild_id: str,
        channel_id: str,
    ) -> OverridableConfig:
        config = OverridableConfig(
            every=self.every,
            max=self.max,
            chance=self.chance,
            special=self.special,
            special_chance=self.special_chance,
        )
        if scene := self.scene_config.get(platform):
            config.merge(scene)
        if scene := self.scene_config.get(f"{platform}:guild:{guild_id}"):
            config.merge(scene)
        if scene := self.scene_config.get(f"{platform}:channel:{channel_id}"):
            config.merge(scene)
        return config

    def is_ignored_in(
        self,
        platform: str,
        guild_id: str,
        channel_id: str,
        message: Sequence[Element],
    ) -> bool:
        if match_blacklist(self.blacklist, message):
            return True
        if config := self.scene_config.get(platform):  # noqa: SIM102
            if match_blacklist(config.blacklist, message):
                return True
        if config := self.scene_config.get(f"{platform}:guild:{guild_id}"):  # noqa: SIM102
            if match_blacklist(config.blacklist, message):
                return True
        if config := self.scene_config.get(f"{platform}:channel:{channel_id}"):  # noqa: SIM102
            if match_blacklist(config.blacklist, message):
                return True
        return False


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


type Comparator = Callable[[Sequence[Element], Sequence[Element]], bool]
type Condition = Callable[[Sequence[Element]], bool]
type Handler = Callable[[MessageCreatedEvent], Awaitable[None]]
metadata("", config=Config)
CONFIG = plugin_config(Config)
RUN_ID = random.randrange(-0x80000000, 0x80000000)
COMPARATOR_REGISTRY = dict[str, Comparator]()
CONDITION_REGISTRY = dict[str, Condition]()
HANDLER_REGISTRY = dict[str, Handler]()
ALREADY_COUNTED = ContextVar("ALREADY_COUNTED", default=False)


def is_same(adapter: str, received: Sequence[Element], recorded: LastMessage) -> bool:
    if recorded.run_id != RUN_ID:
        return False
    if comparator := COMPARATOR_REGISTRY.get(adapter):
        return comparator(received, recorded.chain)
    if len(received) != len(recorded.chain):
        return False
    return all(a == b for a, b in zip(received, recorded.chain, strict=True))


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
