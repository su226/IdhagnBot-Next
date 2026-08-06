import json
from collections.abc import Awaitable, Callable, Generator
from contextvars import ContextVar
from datetime import datetime, timedelta
from functools import cached_property, partial
from importlib import import_module
from types import EllipsisType, FunctionType
from typing import Any, cast

from arclet import letoderea
from arclet.alconna import Alconna, Arparma
from arclet.entari import (
    Account,
    ChannelType,
    MessageChain,
    MessageObject,
    Plugin,
    Reply,
    SendResponse,
    Session,
)
from arclet.entari import Channel as SatoriChannel
from arclet.entari.command.provider import AlconnaSuppiler
from arclet.entari.event.base import (
    ChannelAddedEvent,
    ChannelRemovedEvent,
    ChannelUpdatedEvent,
    FriendRequestEvent,
    GuildAddedEvent,
    GuildEmojiAddedEvent,
    GuildEmojiRemovedEvent,
    GuildEmojiUpdatedEvent,
    GuildMemberAddedEvent,
    GuildMemberRemovedEvent,
    GuildMemberRequestEvent,
    GuildMemberUpdatedEvent,
    GuildRemovedEvent,
    GuildRequestEvent,
    GuildRoleCreatedEvent,
    GuildRoleDeletedEvent,
    GuildRoleUpdatedEvent,
    GuildUpdatedEvent,
    InteractionButtonEvent,
    InteractionCommandArgvEvent,
    InteractionCommandMessageEvent,
    InternalEvent,
    LoginAddedEvent,
    LoginRemovedEvent,
    LoginUpdatedEvent,
    MessageCreatedEvent,
    MessageDeletedEvent,
    MessageUpdatedEvent,
    ReactionAddedEvent,
    ReactionRemovedEvent,
    SatoriEvent,
)
from arclet.entari.event.command import CommandOutput, CommandParse
from arclet.letoderea import SUBSCRIBER, Contexts, Propagator, Subscriber
from entari_plugin_database import (
    AsyncSession,
    Base,
    Mapped,
    SqlalchemyService,
    get_session,
    mapped_column,
)  # entari: plugin
from loguru import logger
from satori import MessageReceipt
from sqlalchemy import ForeignKeyConstraint, delete, desc, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from idhagnbot.hook import hook_subscribers
from idhagnbot.webui.dashboard import OverviewNumber, register


class Guild(Base):
    __tablename__ = "idhagnbot_record_guild"
    platform: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str | None]
    avatar: Mapped[str | None]
    updated_at: Mapped[datetime]
    removed_at: Mapped[datetime | None]


class User(Base):
    __tablename__ = "idhagnbot_record_user"
    platform: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str | None]
    nick: Mapped[str | None]
    avatar: Mapped[str | None]
    is_bot: Mapped[bool | None]
    updated_at: Mapped[datetime]


class Channel(Base):
    __tablename__ = "idhagnbot_record_channel"
    platform: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    type: Mapped[ChannelType]
    name: Mapped[str | None]
    parent_id: Mapped[str | None]
    guild_id: Mapped[str | None]
    user_id: Mapped[str | None]
    updated_at: Mapped[datetime]
    removed_at: Mapped[datetime | None]
    __table_args__ = (
        ForeignKeyConstraint(("platform", "guild_id"), (Guild.platform, Guild.id)),
        ForeignKeyConstraint(("platform", "user_id"), (User.platform, User.id)),
    )


class Member(Base):
    __tablename__ = "idhagnbot_record_member"
    platform: Mapped[str] = mapped_column(primary_key=True)
    guild_id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)
    nick: Mapped[str | None]
    avatar: Mapped[str | None]
    joined_at: Mapped[datetime | None]
    updated_at: Mapped[datetime]
    removed_at: Mapped[datetime | None]
    __table_args__ = (
        ForeignKeyConstraint(("platform", "guild_id"), (Guild.platform, Guild.id)),
        ForeignKeyConstraint(("platform", "user_id"), (User.platform, User.id)),
    )


class Role(Base):
    __tablename__ = "idhagnbot_record_role"
    platform: Mapped[str] = mapped_column(primary_key=True)
    guild_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str | None]
    updated_at: Mapped[datetime]
    removed_at: Mapped[datetime | None]
    __table_args__ = (
        ForeignKeyConstraint(("platform", "guild_id"), (Guild.platform, Guild.id)),
    )


class MemberRole(Base):
    __tablename__ = "idhagnbot_record_member_role"
    platform: Mapped[str] = mapped_column(primary_key=True)
    guild_id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)
    role_id: Mapped[str] = mapped_column(primary_key=True)
    updated_at: Mapped[datetime]
    removed_at: Mapped[datetime | None]
    __table_args__ = (
        ForeignKeyConstraint(
            ("platform", "guild_id", "role_id"),
            (Role.platform, Role.guild_id, Role.id),
        ),
        ForeignKeyConstraint(("platform", "user_id"), (User.platform, User.id)),
    )


class Message(Base):
    __tablename__ = "idhagnbot_record_message"
    platform: Mapped[str] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    current_revision: Mapped[int | None]
    user_id: Mapped[str]
    outgoing: Mapped[bool]
    run_id: Mapped[int | None]
    __table_args__ = (
        ForeignKeyConstraint(
            ("platform", "channel_id"),
            (Channel.platform, Channel.id),
        ),
        ForeignKeyConstraint(("platform", "user_id"), (User.platform, User.id)),
        ForeignKeyConstraint(("run_id",), ("idhagnbot_record_run.id",)),
        ForeignKeyConstraint(
            ("platform", "channel_id", "id", "current_revision"),
            (
                "idhagnbot_record_message_revision.platform",
                "idhagnbot_record_message_revision.channel_id",
                "idhagnbot_record_message_revision.message_id",
                "idhagnbot_record_message_revision.revision",
            ),
            use_alter=True,
        ),
    )


class MessageRevision(Base):
    __tablename__ = "idhagnbot_record_message_revision"
    platform: Mapped[str] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str]
    referrer: Mapped[str | None]
    created_at: Mapped[datetime]
    deleted_at: Mapped[datetime | None]
    deleted_by: Mapped[str | None]

    @cached_property
    def chain(self) -> MessageChain:
        return MessageChain.of(self.content)

    __table_args__ = (
        ForeignKeyConstraint(
            ("platform", "channel_id", "message_id"),
            (Message.platform, Message.channel_id, Message.id),
        ),
        ForeignKeyConstraint(("platform", "deleted_by"), (User.platform, User.id)),
    )


class Run(Base):
    __tablename__ = "idhagnbot_record_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_at: Mapped[datetime]
    platform: Mapped[str | None]
    channel_id: Mapped[str | None]
    message_id: Mapped[str | None]
    plugin_id: Mapped[str]
    module: Mapped[str]
    lineno: Mapped[str]
    command_name: Mapped[str | None]
    command_alias: Mapped[str | None]
    command_output_type: Mapped[str | None]
    __table_args__ = (
        ForeignKeyConstraint(
            ("platform", "channel_id", "message_id"),
            (Message.platform, Message.channel_id, Message.id),
            use_alter=True,
        ),
    )


class Emoji(Base):
    __tablename__ = "idhagnbot_record_emoji"
    platform: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str | None]
    updated_at: Mapped[datetime]


class GuildEmoji(Base):
    __tablename__ = "idhagnbot_record_guild_emoji"
    platform: Mapped[str] = mapped_column(primary_key=True)
    guild_id: Mapped[str] = mapped_column(primary_key=True)
    emoji_id: Mapped[str] = mapped_column(primary_key=True)
    updated_at: Mapped[datetime]
    removed_at: Mapped[datetime | None]
    __table_args__ = (
        ForeignKeyConstraint(("platform", "guild_id"), (Guild.platform, Guild.id)),
        ForeignKeyConstraint(("platform", "emoji_id"), (Emoji.platform, Emoji.id)),
    )


class Reaction(Base):
    __tablename__ = "idhagnbot_record_reaction"
    platform: Mapped[str] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(primary_key=True)
    emoji_id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)
    added_at: Mapped[datetime]
    removed_at: Mapped[datetime | None]
    __table_args__ = (
        ForeignKeyConstraint(
            ("platform", "channel_id", "message_id"),
            (Message.platform, Message.channel_id, Message.id),
        ),
        ForeignKeyConstraint(("platform", "emoji_id"), (Emoji.platform, Emoji.id)),
        ForeignKeyConstraint(("platform", "user_id"), (User.platform, User.id)),
    )


def construct[T: Base](t: type[T], **kw: Any) -> T:
    return t(**{k: v for k, v in kw.items() if v is not ...})


def to_datetime(
    timestamp: float | EllipsisType | None,
) -> datetime | EllipsisType | None:
    if timestamp is None or timestamp is ...:
        return timestamp
    return datetime.fromtimestamp(timestamp / 1000)


async def record_noop(event: SatoriEvent, db: AsyncSession) -> None:
    pass


async def record_generic(
    event: SatoriEvent,
    db: AsyncSession,
    record_guild: bool = True,
    record_channel: bool = True,
    record_login: bool = True,
    record_user: bool = True,
    record_member: bool = True,
    record_operator: bool = True,
    record_role: bool = True,
    record_emoji: bool = True,
) -> None:
    if record_guild and event.guild is not None:
        await db.merge(
            construct(
                Guild,
                platform=event.login.platform,
                id=event.guild.id,
                name=event.guild._raw_data.get("name", ...),
                avatar=event.guild._raw_data.get("avatar", ...),
                updated_at=event.timestamp,
                removed_at=None,
            ),
        )
    if record_channel and event.channel is not None:
        await db.merge(
            construct(
                Channel,
                platform=event.login.platform,
                id=event.channel.id,
                type=event.channel.type,
                name=event.channel._raw_data.get("name", ...),
                parent_id=event.channel._raw_data.get("parent_id", ...),
                guild_id=event.guild.id if event.guild else None,
                user_id=event.user.id if event.user and not event.guild else None,
                updated_at=event.timestamp,
                removed_at=None,
            ),
        )
    if record_login:
        await db.merge(
            construct(
                User,
                platform=event.login.platform,
                id=event.login.user.id,
                name=event.login.user._raw_data.get("name", ...),
                nick=event.login.user._raw_data.get("nick", ...),
                avatar=event.login.user._raw_data.get("avatar", ...),
                is_bot=event.login.user._raw_data.get("is_bot", ...),
                updated_at=event.timestamp,
            ),
        )
    if record_user and event.user is not None:
        await db.merge(
            construct(
                User,
                platform=event.login.platform,
                id=event.user.id,
                name=event.user._raw_data.get("name", ...),
                nick=event.user._raw_data.get("nick", ...),
                avatar=event.user._raw_data.get("avatar", ...),
                is_bot=event.user._raw_data.get("is_bot", ...),
                updated_at=event.timestamp,
            ),
        )
    if (
        record_member
        and event.member is not None
        and event.guild is not None
        and event.user is not None
    ):
        await db.merge(
            construct(
                Member,
                platform=event.login.platform,
                guild_id=event.guild.id,
                user_id=event.user.id,
                nick=event.member._raw_data.get("nick", ...),
                avatar=event.member._raw_data.get("avatar", ...),
                joined_at=to_datetime(event.member._raw_data.get("joined_at", ...)),
                updated_at=event.timestamp,
                removed_at=None,
            ),
        )
        for role in event.member.roles:
            await db.merge(
                construct(
                    Role,
                    platform=event.login.platform,
                    guild_id=event.guild.id,
                    id=role.id,
                    name=role._raw_data.get("name", ...),
                    updated_at=event.timestamp,
                    removed_at=None,
                ),
            )
            await db.merge(
                MemberRole(
                    platform=event.login.platform,
                    guild_id=event.guild.id,
                    user_id=event.user.id,
                    role_id=role.id,
                    updated_at=event.timestamp,
                    removed_at=None,
                ),
            )
    if record_operator and event.guild is not None and event.operator is not None:
        await db.merge(
            construct(
                User,
                platform=event.login.platform,
                id=event.operator.id,
                name=event.operator._raw_data.get("name", ...),
                nick=event.operator._raw_data.get("nick", ...),
                avatar=event.operator._raw_data.get("avatar", ...),
                is_bot=event.operator._raw_data.get("is_bot", ...),
                updated_at=event.timestamp,
            ),
        )
        await db.merge(
            Member(
                platform=event.login.platform,
                guild_id=event.guild.id,
                user_id=event.operator.id,
                updated_at=event.timestamp,
                removed_at=None,
            ),
        )
    if record_role and event.role is not None and event.guild is not None:
        await db.merge(
            construct(
                Role,
                platform=event.login.platform,
                guild_id=event.guild.id,
                id=event.role.id,
                name=event.role._raw_data.get("name", ...),
                updated_at=event.timestamp,
                removed_at=None,
            ),
        )
    if record_emoji and event.emoji is not None:
        await db.merge(
            construct(
                Emoji,
                platform=event.login.platform,
                id=event.emoji.id,
                name=event.emoji._raw_data.get("name", ...),
                updated_at=event.timestamp,
            ),
        )


async def delete_channel(event: ChannelRemovedEvent, db: AsyncSession) -> None:
    await record_generic(event, db, record_channel=False)
    await db.merge(
        construct(
            Channel,
            platform=event.login.platform,
            id=event.channel.id,
            type=event.channel.type,
            name=event.channel._raw_data.get("name", ...),
            parent_id=event.channel._raw_data.get("parent_id", ...),
            guild_id=event.guild.id if event.guild else None,
            deleted_at=event.timestamp,
        ),
    )


async def record_guild_emoji(
    event: GuildEmojiAddedEvent | GuildEmojiUpdatedEvent,
    db: AsyncSession,
) -> None:
    await record_generic(event, db)
    await db.merge(
        GuildEmoji(
            platform=event.login.platform,
            guild_id=event.guild.id,
            emoji_id=event.emoji.id,
            updated_at=event.timestamp,
            removed_at=None,
        ),
    )


async def delete_guild_emoji(event: GuildEmojiRemovedEvent, db: AsyncSession) -> None:
    await record_generic(event, db)
    await db.merge(
        GuildEmoji(
            platform=event.login.platform,
            guild_id=event.guild.id,
            emoji_id=event.emoji.id,
            removed_at=event.timestamp,
        ),
    )


async def delete_guild(event: GuildRemovedEvent, db: AsyncSession) -> None:
    await record_generic(event, db, record_guild=False)
    await db.merge(
        construct(
            Guild,
            platform=event.login.platform,
            id=event.guild.id,
            name=event.guild._raw_data.get("name", ...),
            avatar=event.guild._raw_data.get("avatar", ...),
            removed_at=event.timestamp,
        ),
    )


async def delete_guild_member(event: GuildMemberRemovedEvent, db: AsyncSession) -> None:
    await record_generic(event, db, record_member=False)
    await db.merge(
        Member(
            platform=event.login.platform,
            guild_id=event.guild.id,
            user_id=event.user.id,
            removed_at=event.timestamp,
        ),
    )


async def delete_guild_role(event: GuildRoleDeletedEvent, db: AsyncSession) -> None:
    await record_generic(event, db, record_role=False)
    await db.merge(
        construct(
            Role,
            platform=event.login.platform,
            guild_id=event.guild.id,
            id=event.role.id,
            name=event.role._raw_data.get("name", ...),
            removed_at=event.timestamp,
        ),
    )


async def do_create_message(
    db: AsyncSession,
    *,
    platform: str,
    channel_id: str,
    user_id: str,
    message_id: str,
    content: str,
    created_at: datetime,
    referrer: Any | None,
    outgoing: bool,
    run_id: int | None,
) -> None:
    await db.execute(
        update(Message)
        .where(
            Message.platform == platform,
            Message.channel_id == channel_id,
            Message.id == message_id,
        )
        .values(current_revision=None),
    )
    await db.execute(
        delete(MessageRevision).where(
            MessageRevision.platform == platform,
            MessageRevision.channel_id == channel_id,
            MessageRevision.message_id == message_id,
        ),
    )
    await db.execute(
        delete(Message).where(
            Message.platform == platform,
            Message.channel_id == channel_id,
            Message.id == message_id,
        ),
    )
    referrer = json.dumps(referrer) if referrer else None
    message = Message(
        platform=platform,
        channel_id=channel_id,
        id=message_id,
        user_id=user_id,
        outgoing=outgoing,
        run_id=run_id,
    )
    revision = MessageRevision(
        platform=platform,
        channel_id=channel_id,
        message_id=message_id,
        revision=1,
        content=content,
        created_at=created_at,
        deleted_at=None,
        referrer=referrer,
    )
    db.add(message)
    db.add(revision)
    await db.flush()
    message.current_revision = revision.revision
    db.add(message)


async def create_message(
    event: MessageCreatedEvent | InteractionCommandMessageEvent,
    db: AsyncSession,
) -> None:
    await record_generic(event, db)
    await do_create_message(
        db,
        platform=event.login.platform,
        channel_id=event.channel.id,
        user_id=event.user.id,
        message_id=event.message.id,
        content=event.message.content,
        created_at=event.message.created_at or event.timestamp,
        referrer=event.referrer,
        outgoing=False,
        run_id=None,
    )


async def update_message(event: MessageUpdatedEvent, db: AsyncSession) -> None:
    await record_generic(event, db)
    revision = await db.scalar(
        select(MessageRevision)
        .where(
            MessageRevision.platform == event.login.platform,
            MessageRevision.channel_id == event.channel.id,
            MessageRevision.message_id == event.message.id,
        )
        .order_by(desc(MessageRevision.revision))
        .limit(1),
    )
    timestamp = event.message.updated_at or event.timestamp
    if revision is not None:
        revision.deleted_at = timestamp
        revision.deleted_by = event.user.id
        db.add(revision)
        revision_number = revision.revision + 1
    else:
        revision_number = 1
    referrer = json.dumps(event.message.referrer) if event.message.referrer else None
    revision = MessageRevision(
        platform=event.login.platform,
        channel_id=event.channel.id,
        message_id=event.message.id,
        revision=revision_number,
        content=event.message.content,
        created_at=event.message.created_at or event.timestamp,
        deleted_at=None,
        referrer=referrer,
    )
    db.add(revision)
    await db.flush()
    message = await db.merge(
        Message(
            platform=event.login.platform,
            channel_id=event.channel.id,
            id=event.message.id,
            current_revision=revision.revision,
            user_id=event.user.id,
            outgoing=False,
            run_id=None,
        ),
    )
    db.add(message)


async def delete_message(event: MessageUpdatedEvent, db: AsyncSession) -> None:
    await record_generic(event, db)
    revision = await db.scalar(
        select(MessageRevision)
        .where(
            MessageRevision.platform == event.login.platform,
            MessageRevision.channel_id == event.channel.id,
            MessageRevision.message_id == event.message.id,
        )
        .order_by(desc(MessageRevision.revision))
        .limit(1),
    )
    if revision is not None:
        revision.deleted_at = event.timestamp
        revision.deleted_by = event.operator.id if event.operator else None
        db.add(revision)


async def record_reaction(event: ReactionAddedEvent, db: AsyncSession) -> None:
    await record_generic(event, db)
    await db.merge(
        Reaction(
            platform=event.login.platform,
            channel_id=event.channel.id,
            message_id=event.message.id,
            emoji_id=event.emoji.id,
            user_id=event.user.id,
            added_at=event.timestamp,
        ),
    )


async def delete_reaction(event: ReactionRemovedEvent, db: AsyncSession) -> None:
    await record_generic(event, db)
    await db.merge(
        Reaction(
            platform=event.login.platform,
            channel_id=event.channel.id,
            message_id=event.message.id,
            emoji_id=event.emoji.id,
            user_id=event.user.id,
            removed_at=event.timestamp,
        ),
    )


@letoderea.on(SatoriEvent, priority=-950)
async def record_resources(event: SatoriEvent, db: AsyncSession) -> None:
    try:
        event_t = type(event)
        recorder = RECORDER_MAP.get(event_t)
        if recorder is None:
            logger.warning(f"Unsupported event to record: {event_t}")
            return
        await recorder(event, db)
        await db.commit()
    except SQLAlchemyError:
        logger.opt(exception=True).warning("记录资源失败")


type Recorder[T: SatoriEvent] = Callable[[T, AsyncSession], Awaitable[None]]
RECORDER_MAP: dict[type[SatoriEvent], Recorder[Any]] = {
    ChannelAddedEvent: record_generic,
    ChannelUpdatedEvent: record_generic,
    ChannelRemovedEvent: delete_channel,
    GuildEmojiAddedEvent: record_guild_emoji,
    GuildEmojiUpdatedEvent: record_guild_emoji,
    GuildEmojiRemovedEvent: delete_guild_emoji,
    FriendRequestEvent: record_generic,
    GuildAddedEvent: record_generic,
    GuildUpdatedEvent: record_generic,
    GuildRemovedEvent: delete_guild,
    GuildRequestEvent: record_generic,
    GuildMemberAddedEvent: record_generic,
    GuildMemberUpdatedEvent: record_generic,
    GuildMemberRemovedEvent: delete_guild_member,
    GuildMemberRequestEvent: partial(record_generic, record_member=False),
    GuildRoleCreatedEvent: record_generic,
    GuildRoleUpdatedEvent: record_generic,
    GuildRoleDeletedEvent: delete_guild_role,
    InteractionButtonEvent: record_generic,
    InteractionCommandArgvEvent: record_generic,
    InteractionCommandMessageEvent: create_message,
    LoginAddedEvent: record_noop,
    LoginRemovedEvent: record_noop,
    LoginUpdatedEvent: record_noop,
    MessageCreatedEvent: create_message,
    MessageUpdatedEvent: update_message,
    MessageDeletedEvent: delete_message,
    ReactionAddedEvent: record_reaction,
    ReactionRemovedEvent: delete_reaction,
    InternalEvent: record_noop,
}


@letoderea.on(SendResponse)
async def record_send(
    account: Account,
    channel: SatoriChannel,
    result: list[MessageReceipt],
    db: AsyncSession,
    session: Session | None = None,
) -> None:
    now = datetime.now()
    if session is None:
        run_id = None
    else:
        run_id = getattr(session.event, "idhagnbot_run_id", None)
    try:
        for message in result:
            await do_create_message(
                db,
                platform=account.platform,
                channel_id=channel.id,
                user_id=account.self_id,
                message_id=message.id,
                content=message.content,
                created_at=message.created_at or now,
                referrer=None,
                outgoing=True,
                run_id=run_id,
            )
        await db.commit()
    except SQLAlchemyError:
        logger.opt(exception=True).warning("记录资源失败")


async def record_command_run(
    plugin_id: str,
    subscriber: Subscriber,
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
    db: SqlalchemyService,
    arparma: Arparma[MessageChain],
    output_type: str,
) -> None:
    logger.debug(f"Recording run of {subscriber}")
    fn = cast("FunctionType", subscriber.callable_target)
    module = fn.__module__
    lineno = fn.__code__.co_firstlineno
    command_name = arparma.source.name
    command_alias = arparma.header_match.origin
    run = Run(
        run_at=datetime.now(),
        channel_id=session.event.channel.id,
        message_id=session.event.message.id,
        plugin_id=plugin_id,
        module=module,
        lineno=lineno,
        command_name=command_name,
        command_alias=command_alias,
        command_output_type=output_type,
    )
    await db.add(run)
    if getattr(session.event, "idhagnbot_run_id", None) is not None:
        logger.warning("Event has run more than once.")
    setattr(session.event, "idhagnbot_run_id", run.id)


def get_subscriber_plugin(subscriber: Subscriber) -> str:
    module = import_module(subscriber.callable_target.__module__)
    return module.__plugin__.id


async def record_non_command_run(
    plugin_id: str,
    subscriber: Subscriber,
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
    db: SqlalchemyService,
) -> None:
    logger.debug(f"Recording run of {subscriber}")
    fn = cast("FunctionType", subscriber.callable_target)
    module = fn.__module__
    lineno = fn.__code__.co_firstlineno
    run = Run(
        run_at=datetime.now(),
        channel_id=session.event.channel.id,
        message_id=session.event.message.id,
        plugin_id=plugin_id,
        module=module,
        lineno=lineno,
        command_name=None,
        command_alias=None,
        command_output_type=None,
    )
    await db.add(run)
    if getattr(session.event, "idhagnbot_run_id", None) is not None:
        logger.warning("Event has run more than once.")
    setattr(session.event, "idhagnbot_run_id", run.id)


class RecordNonCommandPropagator(Propagator):
    def __init__(self, priority: int) -> None:
        self.plugin_id: str | None = None
        self.priority = priority

    async def record(
        self,
        session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
        db: SqlalchemyService,
        contexts: Contexts,
    ) -> None:
        subscriber = contexts[SUBSCRIBER]
        if self.plugin_id is None:
            self.plugin_id = get_subscriber_plugin(subscriber)
        await record_non_command_run(self.plugin_id, subscriber, session, db)

    def compose(self) -> Generator[tuple[Callable[..., Any], bool, int]]:
        yield self.record, True, self.priority


def recorded_non_command[T: Callable[..., Any]](
    priority: int = 100,
) -> Callable[[T], T]:
    return letoderea.propagate(RecordNonCommandPropagator(priority))


async def record_non_message_run(
    plugin_id: str,
    subscriber: Subscriber,
    session: Session[SatoriEvent],
    db: SqlalchemyService,
) -> None:
    logger.debug(f"Recording run of {subscriber}")
    fn = cast("FunctionType", subscriber.callable_target)
    module = fn.__module__
    lineno = fn.__code__.co_firstlineno
    run = Run(
        run_at=datetime.now(),
        channel_id=session.event.channel.id
        if session.event.channel is not None
        else None,
        message_id=session.event.message.id
        if session.event.message is not None
        else None,
        plugin_id=plugin_id,
        module=module,
        lineno=lineno,
        command_name=None,
        command_alias=None,
        command_output_type=None,
    )
    await db.add(run)
    if getattr(session.event, "idhagnbot_run_id", None) is not None:
        logger.warning("Event has run more than once.")
    setattr(session.event, "idhagnbot_run_id", run.id)


class RecordNonMessagePropagator(Propagator):
    def __init__(self, priority: int) -> None:
        self.plugin_id: str | None = None
        self.priority = priority

    async def record(
        self,
        session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
        db: SqlalchemyService,
        contexts: Contexts,
    ) -> None:
        subscriber = contexts[SUBSCRIBER]
        if self.plugin_id is None:
            self.plugin_id = get_subscriber_plugin(subscriber)
        await record_non_command_run(self.plugin_id, subscriber, session, db)

    def compose(self) -> Generator[tuple[Callable[..., Any], bool, int]]:
        yield self.record, True, self.priority


def recorded_non_message[T: Callable[..., Any]](
    priority: int = 100,
) -> Callable[[T], T]:
    return letoderea.propagate(RecordNonMessagePropagator(priority))


@letoderea.on(CommandParse)
async def handle_command_parse(
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
    alconna: Alconna[MessageChain],
    arparma: Arparma[MessageChain],
) -> None:
    arparmas = getattr(session.event, "idhagnbot_arparmas", None)
    if arparmas is None:
        arparmas = {}
        setattr(session.event, "idhagnbot_arparmas", arparmas)
    arparmas[alconna.path] = arparma


recorded_subscriber: ContextVar[tuple[str, Subscriber] | None] = ContextVar(
    "recorded_subscriber",
    default=None,
)


@letoderea.on(CommandOutput)
async def handle_command_output(
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
    db: SqlalchemyService,
    alconna: Alconna[MessageChain],
    type: str,  # noqa: A002
) -> None:
    recorded = recorded_subscriber.get()
    if recorded is None:
        logger.warning("Not record output run due to missing subscriber.")
        return
    arparmas = getattr(session.event, "idhagnbot_arparmas", None)
    if arparmas is None:
        logger.warning("Not record output run due to missing arparma.")
        return
    arparma = arparmas.get(alconna.path)
    if arparma is None:
        logger.warning("Not record output run due to missing arparma.")
        return
    plugin_id, subscriber = recorded
    await record_command_run(plugin_id, subscriber, session, db, arparma, type)


class AlconnaExecuteRecorder(Propagator):
    def __init__(self, plugin_id: str, subscriber: Subscriber) -> None:
        self.plugin_id = plugin_id
        self.subscriber = subscriber

    def compose(self) -> Generator[tuple[Callable[..., Awaitable[None]], bool, int]]:
        yield self.record, True, 90

    async def record(
        self,
        session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
        db: SqlalchemyService,
        arparma: Arparma[MessageChain],
    ) -> None:
        await record_command_run(
            self.plugin_id,
            self.subscriber,
            session,
            db,
            arparma,
            "execute",
        )


PLUGIN = Plugin.current()


@PLUGIN.collect
@hook_subscribers
def hook_commands(plugin_id: str, subscriber: Subscriber) -> None:
    try:
        propagator = subscriber.get_propagator(AlconnaSuppiler.supply)
    except ValueError:
        return

    async def supply(
        message: MessageChain,
        origin: MessageObject | None = None,
        session: Session | None = None,
        reply: Reply | None = None,
    ) -> Any:
        token = recorded_subscriber.set((plugin_id, subscriber))
        try:
            return await orig_supply(message, origin, session, reply)
        finally:
            recorded_subscriber.reset(token)

    logger.trace(f"Hooking {subscriber} for recording runs.")
    orig_supply = propagator._callable_target
    propagator._callable_target = supply
    execute_recorder = AlconnaExecuteRecorder(plugin_id, subscriber)
    PLUGIN.collect(subscriber.propagate(execute_recorder))

    @PLUGIN.collect
    def restore_suppiler() -> None:
        propagator._callable_target = orig_supply


@register("chat_record:message_incoming")
async def get_message_incoming() -> OverviewNumber:
    time_now = datetime.now()
    time_start = time_now - timedelta(1)
    async with get_session() as sql:
        result = await sql.execute(
            select(func.count())
            .select_from(Message)
            .join(
                MessageRevision,
                (Message.platform == MessageRevision.platform)
                & (Message.channel_id == MessageRevision.channel_id)
                & (Message.id == MessageRevision.message_id)
                & (MessageRevision.revision == 1),
            )
            .where(
                MessageRevision.created_at >= time_start,
                MessageRevision.created_at <= time_now,
                ~Message.outgoing,
            ),
        )
        count = result.scalar_one()
    return OverviewNumber(
        name="24h 收到消息",
        icon="message",
        type="number",
        value=count,
    )


@register("chat_record:message_outgoing")
async def get_message_outgoing() -> OverviewNumber:
    time_now = datetime.now()
    time_start = time_now - timedelta(1)
    async with get_session() as sql:
        result = await sql.execute(
            select(func.count())
            .select_from(Message)
            .join(
                MessageRevision,
                (Message.platform == MessageRevision.platform)
                & (Message.channel_id == MessageRevision.channel_id)
                & (Message.id == MessageRevision.message_id)
                & (MessageRevision.revision == 1),
            )
            .where(
                MessageRevision.created_at >= time_start,
                MessageRevision.created_at <= time_now,
                Message.outgoing,
            ),
        )
        count = result.scalar_one()
    return OverviewNumber(
        name="24h 发出消息",
        icon="message",
        type="number",
        value=count,
    )
