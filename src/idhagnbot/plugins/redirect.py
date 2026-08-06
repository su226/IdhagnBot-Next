from datetime import datetime, timedelta
from typing import Annotated

from arclet import letoderea
from arclet.alconna import Alconna, Args, CommandMeta, Subcommand
from arclet.entari import Entari, Session, command, filter_
from arclet.entari.command import Match
from arclet.letoderea import Depends
from entari_plugin_database import (
    AsyncSession,
    Base,
    Mapped,
    mapped_column,
    select,
)  # entari: plugin
from entari_plugin_permission import require_permission
from entari_plugin_user import User  # entari: plugin
from entari_plugin_user.models import Bind
from satori.exception import ActionFailed
from sqlalchemy import delete

from idhagnbot.i18n import bound_lang
from idhagnbot.plugins.record import Channel, Guild
from idhagnbot.support import get_bot_on

L = bound_lang("idhagnbot_redirect")


class Redirect(Base):
    __tablename__ = "idhagnbot_redirect_redirect"
    platform: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)
    target_platform: Mapped[str]
    target_guild: Mapped[str]
    target_channel: Mapped[str | None]
    expire_at: Mapped[datetime]


redirect_alc = Alconna(
    "in",
    Subcommand("direct|私聊"),
    Subcommand("guild|群组", Args["guild", str]),
    Subcommand("channel|频道", Args["channel", str]),
    meta=CommandMeta(
        description="改变执行命令的环境。",
        extra={
            "idhagnbot_i18n_description": "idhagnbot_redirect:command_brief_redirect",
            "idhagnbot_i18n_names": {
                "in": "en-US",
                "进入": "zh-CN",
            },
        },
    ),
)
redirect_alc.shortcut("进入", command="in")
redirect_cmd = command.mount(redirect_alc, skip_for_unmatch=False).as_execute()
redirect_cmd.propagators.append(filter_.direct)


@redirect_cmd.assign("$main")
@letoderea.propagate(require_permission("idhagnbot.redirect.view", prompt=True))
async def redirect_root(
    session: Session,
    db: AsyncSession,
) -> str:
    redirect = await db.get(Redirect, (session.account.platform, session.user.id))
    if redirect is None:
        return L("current_direct")
    if redirect.target_channel is None:
        guild_data = await db.get(
            Guild,
            (redirect.target_platform, redirect.target_guild),
        )
        guild_name = L("name_unknown")
        if guild_data:
            guild_name = guild_data.name or guild_name
        return L("current_guild").format(guild=guild_name)
    guild_data = await db.get(
        Guild,
        (redirect.target_platform, redirect.target_guild),
    )
    channel_data = await db.get(
        Channel,
        (redirect.target_platform, redirect.target_channel),
    )
    guild_name = L("name_unknown")
    if guild_data:
        guild_name = guild_data.name or guild_name
    channel_name = L("name_unknown")
    if channel_data:
        channel_name = channel_data.name or channel_name
    return L("current_channel").format(guild=guild_name, channel=channel_name)


@redirect_cmd.assign("direct")
@letoderea.propagate(require_permission("idhagnbot.redirect.direct", prompt=True))
async def redirect_direct(
    session: Session,
    db: AsyncSession,
) -> str:
    await db.execute(
        delete(Redirect).where(
            Redirect.platform == session.account.platform,
            Redirect.user_id == session.user.id,
        ),
    )
    await db.commit()
    return L("redirect_direct")


@redirect_cmd.assign("guild")
@letoderea.propagate(require_permission("idhagnbot.redirect.guild", prompt=True))
async def redirect_guild(
    app: Entari,
    session: Session,
    guild: Match[str],
    db: AsyncSession,
    user: User,
) -> str:
    splited = guild.result.split(":", 1)
    if len(splited) == 2:
        target_platform, target_guild = splited
    else:
        target_platform = session.account.platform
        target_guild = guild.result
    if user.authority < 5:
        if target_platform != session.account.platform:
            target_user = await db.scalar(
                select(Bind)
                .where(
                    Bind.bind_id == user.id,
                    Bind.platform == target_platform,
                )
                .limit(1),
            )
            if target_user is None:
                return L("error_no_user")
            target_user_id = target_user.platform_id
            target_account = get_bot_on(target_platform)
            if target_account is None:
                return L("error_no_bot")
        else:
            target_user_id = session.user.id
            target_account = session.account
        try:
            await target_account.guild_member_get(target_guild, target_user_id)
        except ActionFailed:
            return L("error_not_guild_member")
        guild_data = await db.get(Guild, (target_platform, target_guild))
        guild_name = L("name_unknown")
        if guild_data:
            guild_name = guild_data.name or guild_name
    else:
        if target_platform != session.account.platform:
            target_account = get_bot_on(target_platform)
            if target_account is None:
                return L("error_no_bot")
        else:
            target_account = session.account
        try:
            guild_info = await target_account.guild_get(target_guild)
        except ActionFailed:
            return L("error_no_guild")
        guild_name = guild_info.name or L("name_unknown")
    await db.merge(
        Redirect(
            platform=session.account.platform,
            user_id=session.user.id,
            target_platform=target_platform,
            target_guild=target_guild,
            target_channel=None,
            expire_at=datetime.now() + timedelta(minutes=10),
        ),
    )
    return L("redirect_guild").format(guild=guild_name)


@redirect_cmd.assign("channel")
@letoderea.propagate(require_permission("idhagnbot.redirect.channel", prompt=True))
async def redirect_channel(
    app: Entari,
    session: Session,
    channel: Match[str],
    db: AsyncSession,
    user: User,
) -> str:
    splited = channel.result.split(":", 1)
    if len(splited) == 2:
        target_platform, target_channel = splited
    else:
        target_platform = session.account.platform
        target_channel = channel.result
    channel_data = await db.get(Channel, (target_platform, target_channel))
    if channel_data is None:
        return L("error_no_channel")
    target_guild = channel_data.guild_id
    if target_guild is None:
        return L("error_not_public")
    if user.authority < 5:
        if target_platform != session.account.platform:
            target_user = await db.scalar(
                select(Bind)
                .where(
                    Bind.bind_id == user.id,
                    Bind.platform == target_platform,
                )
                .limit(1),
            )
            if target_user is None:
                return L("error_no_user")
            target_user_id = target_user.platform_id
            target_account = get_bot_on(target_platform)
            if target_account is None:
                return L("error_no_bot")
        else:
            target_user_id = session.user.id
            target_account = session.account
        try:
            await target_account.guild_member_get(target_guild, target_user_id)
        except ActionFailed:
            return L("error_not_channel_member")
    guild_data = await db.get(Guild, (target_platform, target_guild))
    guild_name = L("name_unknown")
    if guild_data:
        guild_name = guild_data.name or guild_name
    channel_name = channel_data.name or L("name_unknown")
    await db.merge(
        Redirect(
            platform=session.account.platform,
            user_id=session.user.id,
            target_platform=target_platform,
            target_guild=target_guild,
            target_channel=target_channel,
            expire_at=datetime.now() + timedelta(minutes=10),
        ),
    )
    return L("redirect_channel").format(guild=guild_name, channel=channel_name)


async def guild_id(session: Session, db: AsyncSession) -> tuple[str, str] | None:
    if session.event.guild is None:
        redirect = await db.get(Redirect, (session.account.platform, session.user.id))
        if redirect is not None:
            return (redirect.target_platform, redirect.target_guild)
        return None
    return (session.account.platform, session.event.guild.id)


async def channel_id(session: Session, db: AsyncSession) -> tuple[str, str]:
    if session.event.guild is None:
        redirect = await db.get(Redirect, (session.account.platform, session.user.id))
        if redirect is not None and redirect.target_channel is not None:
            return (redirect.target_platform, redirect.target_channel)
    return (session.account.platform, session.channel.id)


MaybeGuildId = Annotated[tuple[str, str] | None, Depends(guild_id)]
GuildId = Annotated[tuple[str, str], Depends(guild_id)]
ChannelId = Annotated[tuple[str, str], Depends(channel_id)]


async def in_or_redirected_to_guild(guild_id: MaybeGuildId) -> bool:
    return guild_id is not None
