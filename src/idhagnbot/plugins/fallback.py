import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Literal

from aiohttp import ClientError
from arclet import letoderea
from arclet.alconna import Alconna, Args, CommandMeta, command_manager
from arclet.alconna._internal._util import levenshtein
from arclet.entari import (
    ChannelType,
    Session,
    Text,
    command,
    enter_if,
    metadata,
    plugin_config,
)
from arclet.entari import Image as ImageSeg
from arclet.entari.command import AlconnaSuppiler
from arclet.entari.config import EntariConfig
from arclet.entari.event.base import (
    InteractionCommandMessageEvent,
    MessageCreatedEvent,
    SatoriEvent,
)
from arclet.entari.filter.parse import parse_filter
from arclet.entari.plugin import Plugin
from arclet.letoderea import (
    BLOCK,
    Contexts,
    ExceptionEvent,
    ExitState,
    Subscriber,
)
from entari_plugin_database import (
    AsyncSession,
    Base,
    Mapped,
    get_session,
    mapped_column,
)  # entari: plugin
from entari_plugin_permission import (
    Permission,
    require_permission,
    system,
)  # entari: plugin
from entari_plugin_permission.service import AUTH_3
from loguru import logger
from PIL import Image
from pydantic import BaseModel, Field
from satori.element import escape as satori_escape
from satori.exception import ActionFailed
from sqlalchemy import delete
from tarina.trie import Trie

from idhagnbot.hook import hook_subscribers
from idhagnbot.i18n import bound_lang
from idhagnbot.image import paste, to_segment
from idhagnbot.permission import ADMIN
from idhagnbot.plugins.alias import get_aliases, get_prefix, has_command_prefix
from idhagnbot.plugins.record import recorded_non_command
from idhagnbot.plugins.redirect import GuildId, in_or_redirected_to_guild
from idhagnbot.text import escape, render
from idhagnbot.third_party.bilibili_auth import ApiError


class Config(BaseModel):
    show_invalid_command: str = "True"
    show_im_bot: str = "True"
    show_exception: str = "True"
    min_similarity: float | None = 0.6
    ignore_prefix: dict[str, set[str]] = Field(default_factory=dict)
    ignore_bot: bool = True
    ignore_user: set[str] = Field(default_factory=set)


metadata("", config=Config)
CONFIG = plugin_config(Config)
show_invalid_command = parse_filter(CONFIG.show_invalid_command)
show_im_bot = parse_filter(CONFIG.show_im_bot)
show_exception = parse_filter(CONFIG.show_exception)
ignore_prefix: dict[str, Trie[None]] = {}
L = bound_lang("idhagnbot_fallback")
type ExceptionExplain = Callable[[BaseException], str | None]
registered_exception_explains: list[ExceptionExplain] = []


scope = None
prefixes = None
for scope, prefixes in CONFIG.ignore_prefix:
    ignore_prefix[scope] = Trie((x, None) for x in prefixes)
del scope, prefixes


def is_ignored_user(session: Session[Any]) -> bool:
    if session.event.user is None:
        return False
    if CONFIG.ignore_bot and session.event.user.is_bot:
        return True
    platform = session.account.platform
    user_id = session.event.user.id
    return f"{platform}:{user_id}" in CONFIG.ignore_user


def has_ignored_prefix(session: Session[Any]) -> bool:
    if not session.elements:
        return False
    segment = session.elements[0]
    platform = session.account.platform
    guild = (
        f"{platform}:private"
        if session.event.guild is None
        else f"{platform}:{session.event.guild.id}"
    )
    return isinstance(segment, Text) and (
        (
            platform in ignore_prefix
            and bool(ignore_prefix[platform].shortest_prefix(segment.text))
        )
        or (
            guild in ignore_prefix
            and bool(ignore_prefix[guild].shortest_prefix(segment.text))
        )
    )


class ImBotSuppressedUser(Base):
    __tablename__ = "idhagnbot_fallback_im_bot_suppressed_user"
    platform: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)


class ExceptionSuppressedGuild(Base):
    __tablename__ = "idhagnbot_fallback_exception_suppressed_guild"
    platform: Mapped[str] = mapped_column(primary_key=True)
    guild_id: Mapped[str] = mapped_column(primary_key=True)
    until: Mapped[datetime]


async def is_exception_suppressed_in(platform: str, guild_id: str) -> bool:
    async with get_session() as session:
        info = await session.get(ExceptionSuppressedGuild, (platform, guild_id))
        if info and info.until > datetime.now():
            return True
    return False


async def is_im_bot_suppressed_for(platform: str, user_id: str) -> bool:
    async with get_session() as session:
        return bool(await session.get(ImBotSuppressedUser, (platform, user_id)))


def register_exception_explain[T: ExceptionExplain](explain: T) -> T:
    registered_exception_explains.append(explain)
    return explain


@register_exception_explain
def builtin_exception_explain(exception: BaseException) -> str | None:
    if isinstance(exception, ClientError):
        return L("error_type_network")
    if isinstance(exception, ManualException):
        return L("error_type_manual")
    if isinstance(exception, Image.DecompressionBombError):
        return L("error_type_large_image")
    if isinstance(exception, ApiError):
        return L("error_type_bilibili")
    return None


class ManualException(Exception):
    def __init__(self) -> None:
        prefix = EntariConfig.instance.basic.prefix[0]
        super().__init__(f"管理员使用 {prefix}raise 手动触发了错误")


@letoderea.on(ExceptionEvent)
async def send_error(event: ExceptionEvent) -> None:
    if not isinstance(event.origin, SatoriEvent):
        return
    if getattr(event.origin, "idhagnbot_error_sent", False):
        return
    setattr(event.origin, "idhagnbot_error_sent", True)
    setattr(event.origin, "idhagnbot_executed", True)
    if event.origin.channel is None:
        return
    session = Session(event.origin.account, event.origin)
    contexts = Contexts()
    await event.origin.gather(contexts)
    if not await show_exception(
        session,
        contexts["is_reply_me"],
        contexts["is_notice_me"],
    ) or await is_exception_suppressed_in(
        session.account.platform,
        session.event.channel.id,
    ):
        return
    for checker in registered_exception_explains:
        reason = checker(event.exception)
        if reason:
            break
    else:
        reason = L("error_type_unknown")

    header_markup = L("error_markup_header")
    content_markup = L("error_markup_content").format(reason=escape(reason))
    content_fallback = L("error_plain_content").format(reason=reason)
    if session.event.channel.type != ChannelType.DIRECT:
        prefix = get_prefix(session.account.platform)
        content_markup += "\n" + L("error_markup_group").format(prefix=prefix)
        content_fallback += "\n" + L("error_plain_group").format(prefix=prefix)

    def make() -> ImageSeg:
        header = render(
            header_markup,
            "sans",
            32,
            color=(255, 255, 255),
            align="m",
            markup=True,
        )
        content = render(
            content_markup,
            "sans",
            32,
            color=(255, 255, 255),
            box=max(640, header.width),
            markup=True,
        )
        size = (
            max(header.width, content.width) + 64,
            header.height + content.height + 80,
        )
        im = Image.new("RGB", size, (30, 30, 30))
        im.paste((205, 49, 49), (0, 32, im.width, 32 + header.height))
        paste(im, header, (im.width // 2, 32), (0.5, 0))
        im.paste(content, (32, 48 + header.height), content)
        return to_segment(im)

    try:
        await session.send([await asyncio.to_thread(make)])
    except ActionFailed:
        await session.send(satori_escape(content_fallback))


def get_commands(session: Session[Any], prefix: str) -> list[str]:
    names: list[str] = []
    for cmd in command_manager.get_commands():
        names.append(cmd.name)
        names.extend(command_manager.get_shortcut(cmd))
    names.extend(
        alias[len(prefix) :]
        for alias in get_aliases(session)
        if alias.startswith(prefix)
    )
    return names


async def set_executed(
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
) -> None:
    setattr(session.event, "idhagnbot_executed", True)


PLUGIN = Plugin.current()


@PLUGIN.collect
@hook_subscribers
def hook_commands(plugin_id: str, subscriber: Subscriber) -> None:
    try:
        subscriber.get_propagator(AlconnaSuppiler)
    except ValueError:
        return

    logger.trace(f"Hooking {subscriber} for set executed.")
    PLUGIN.collect(
        subscriber.propagate(set_executed, prepend=True, priority=85),
    )


async def check_bad_command(
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
    is_reply_me: bool,
    is_notice_me: bool,
    contexts: Contexts,
) -> bool:
    platform = session.account.platform
    if (
        not getattr(session.event, "idhagnbot_executed", False)
        and not is_ignored_user(session)
        and not has_ignored_prefix(session)
        and (match := has_command_prefix(platform, session.elements))
        and await show_invalid_command(session, is_reply_me, is_notice_me)
    ):
        contexts["idhagnbot_command_prefix_match"] = match
        return True
    return False


@letoderea.on(MessageCreatedEvent, priority=995)
@letoderea.on(InteractionCommandMessageEvent, priority=995)
@letoderea.propagate(require_permission("idhagnbot.fallback.show_bad_command"))
@recorded_non_command()
@enter_if(check_bad_command)
async def send_bad_command(
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
    contexts: Contexts,
) -> ExitState:
    message = L("bad_command")
    if CONFIG.min_similarity is not None:
        prefix, suffix = contexts["idhagnbot_command_prefix_match"]
        command, similarity = max(
            (
                (command, levenshtein(command, suffix))
                for command in get_commands(session, prefix)
            ),
            key=lambda x: x[1],
        )
        if similarity >= CONFIG.min_similarity:
            message += f"\n{L('bad_command_suggestion')}{prefix}{command}"
    await session.send(satori_escape(message))
    return BLOCK


async def check_im_bot(
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
    is_reply_me: bool,
    is_notice_me: bool,
) -> bool:
    platform = session.account.platform
    return (
        not getattr(session.event, "idhagnbot_executed", False)
        and not is_ignored_user(session)
        and not has_ignored_prefix(session)
        and (is_reply_me or is_notice_me)
        and await show_im_bot(session, is_reply_me, is_notice_me)
        and not await is_im_bot_suppressed_for(platform, session.user.id)
    )


@letoderea.on(MessageCreatedEvent, priority=1000)
@letoderea.on(InteractionCommandMessageEvent, priority=1000)
@letoderea.propagate(require_permission("idhagnbot.fallback.show_im_bot"))
@recorded_non_command()
@enter_if(check_im_bot)
async def send_im_bot(
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
) -> ExitState:
    message = L("im_a_bot").format(prefix=get_prefix(session.account.platform))
    await session.send(satori_escape(message))
    return BLOCK


@command.on(
    Alconna(
        "禁用提示",
        meta=CommandMeta(description="禁用“本账号是机器人”提示。", hide=True),
    ),
)
@letoderea.propagate(
    require_permission("idhagnbot.fallback.suppress_im_bot", prompt=True),
)
@enter_if(show_im_bot)
async def handle_suppress_im_bot(session: Session, db: AsyncSession) -> str:
    platform = session.account.platform
    user_id = session.user.id
    if ignored := await db.get(ImBotSuppressedUser, (platform, user_id)):
        await db.delete(ignored)
        await db.commit()
        return L("im_a_bot_restored")
    db.add(ImBotSuppressedUser(platform=platform, user_id=user_id))
    await db.commit()
    return L("im_a_bot_suppressed").format(prefix=get_prefix(session.account.platform))


@command.on(
    Alconna(
        "suppress",
        Args["toggle?", str, ""],
        meta=CommandMeta(
            extra={
                "idhagnbot_i18n_description": (
                    "idhagnbot_fallback:command_brief_suppress_exception"
                ),
            },
        ),
    ),
)
@letoderea.propagate(
    require_permission(
        "idhagnbot.fallback.suppress_exception",
        default_available=False,
        prompt=True,
    ),
)
@enter_if(in_or_redirected_to_guild)
async def handle_suppress_exception(
    session: Session,
    platform_guild_id: GuildId,
    db: AsyncSession,
    toggle: str,
) -> str:
    platform, guild_id = platform_guild_id
    toggle = toggle.lower()
    if toggle in ("true", "t", "1", "yes", "y", "on"):
        until = datetime.now() + timedelta(1)
        await db.merge(
            ExceptionSuppressedGuild(platform=platform, guild_id=guild_id, until=until),
        )
        await db.commit()
        return L("error_suppressed")
    if toggle in ("false", "f", "0", "no", "n", "off"):
        await db.execute(
            delete(ExceptionSuppressedGuild).where(
                ExceptionSuppressedGuild.platform == platform,
                ExceptionSuppressedGuild.guild_id == guild_id,
            ),
        )
        await db.commit()
        return L("error_restored")
    prefix = get_prefix(platform)
    return L("error_suppress_usage").format(prefix=prefix)


system.pre_assign(
    AUTH_3,
    "idhagnbot.fallback.suppress_exception",
    Permission.VISIT | Permission.AVAILABLE,
)
system.pre_assign(
    ADMIN,
    "idhagnbot.fallback.suppress_exception",
    Permission.VISIT | Permission.AVAILABLE,
)


@command.on(
    Alconna(
        "raise",
        Args["confirm?", Literal["confirm"], None],
        meta=CommandMeta(
            extra={
                "idhagnbot_i18n_description": (
                    "idhagnbot_fallback:command_brief_raise_exception"
                ),
            },
        ),
    ),
)
@letoderea.propagate(
    require_permission(
        "idhagnbot.fallback.raise",
        default_available=False,
        prompt=True,
    ),
)
async def handle_raise_exception(
    session: Session,
    confirm: Literal["confirm"] | None,
) -> str:
    if confirm == "confirm":
        raise ManualException
    prefix = get_prefix(session.account.platform)
    return L("error_raise_usage").format(prefix=prefix)
