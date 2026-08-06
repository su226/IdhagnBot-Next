from collections.abc import Iterable
from typing import Any

from arclet import letoderea
from arclet.alconna import Alconna, Args, CommandMeta, Option, store_true
from arclet.entari import MessageEvent, Plugin, command, enter_if
from arclet.entari.command import Match
from arclet.entari.event.base import SatoriEvent
from arclet.letoderea import Contexts, Scope
from arclet.letoderea.scope import SubscriberSlot
from entari_plugin_database import (
    AsyncSession,
    Base,
    Mapped,
    get_session,
    mapped_column,
)  # entari: plugin
from entari_plugin_permission import (
    AUTH_3,
    Permission,
    require_permission,
    system,
)  # entari: plugin
from tarina import LRU, lang

from idhagnbot.i18n import bound_lang, current_locale, get_full_name, get_name
from idhagnbot.permission import ADMIN


class UserLocale(Base):
    __tablename__ = "idhagnbot_i18n_user_locale"
    platform: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)
    locale: Mapped[str]


class GuildLocale(Base):
    __tablename__ = "idhagnbot_i18n_guild_locale"
    platform: Mapped[str] = mapped_column(primary_key=True)
    guild_id: Mapped[str] = mapped_column(primary_key=True)
    locale: Mapped[str]
    force: Mapped[bool]


# TypeError: type '_lru_c.LRU' is not subscriptable
USER_LOCALES: LRU[tuple[str, str], str | None] = LRU(128)
GUILD_LOCALES: LRU[tuple[str, str], tuple[str, bool] | None] = LRU(128)


async def query_guild_locale(
    db: AsyncSession,
    platform: str,
    guild_id: str,
) -> tuple[str, bool] | None:
    try:
        return GUILD_LOCALES[platform, guild_id]
    except KeyError:
        pass
    locale_config = await db.get(GuildLocale, (platform, guild_id))
    locale = (
        None if locale_config is None else (locale_config.locale, locale_config.force)
    )
    GUILD_LOCALES[platform, guild_id] = locale
    return locale


async def query_user_locale(
    db: AsyncSession,
    platform: str,
    user_id: str,
) -> str | None:
    try:
        return USER_LOCALES[platform, user_id]
    except KeyError:
        pass
    locale_config = await db.get(UserLocale, (platform, user_id))
    locale = None if locale_config is None else locale_config.locale
    USER_LOCALES[platform, user_id] = locale
    return locale


async def query_locale(event: SatoriEvent) -> str | None:
    async with get_session() as db:
        platform = event.login.platform
        guild_locale = (
            await query_guild_locale(db, platform, event.guild.id)
            if event.guild is not None
            else None
        )
        if guild_locale is not None and guild_locale[1]:
            return guild_locale[0]
        if user := event.operator or event.user:
            user_locale = await query_user_locale(db, platform, user.id)
            if user_locale is not None:
                return user_locale
        if guild_locale is not None:
            return guild_locale[0]
    return None


_orig_dispatch = letoderea.core.dispatch


async def _dispatch(
    event: Any,
    scope: str | Scope[Any] | None = None,
    slots: Iterable[SubscriberSlot] | None = None,
    inherit_ctx: Contexts | None = None,
) -> None:
    if isinstance(event, SatoriEvent):
        token = current_locale.set(await query_locale(event))
        try:
            await _orig_dispatch(event, scope, slots, inherit_ctx)
        finally:
            current_locale.reset(token)
    else:
        await _orig_dispatch(event, scope, slots, inherit_ctx)


letoderea.core.dispatch = _dispatch  # ty:ignore[invalid-assignment]
PLUGIN = Plugin.current()


@PLUGIN.collect
def reset_dispatch() -> None:
    letoderea.core.dispatch = _orig_dispatch


def format_langs() -> str:
    return "\n".join(
        f"{key}: {name}" if (name := get_name(key)) else key for key in lang.locales
    )


L = bound_lang("idhagnbot_i18n")
LANG_SWITCH_HEADER = (
    "Use {command} <ID> (not name) to switch locale.\nAvailable locales (ID: name):"
)
COMMAND_PREFIX = "/"  # TODO: implement this


@command.on(
    Alconna(
        "lang",
        Args["locale?", str, None],
        Option("--reset", action=store_true, dest="reset", default=False),
        meta=CommandMeta("Get or set user locale."),
    ),
)
@letoderea.propagate(
    require_permission("idhagnbot.i18n.lang", prompt=True),
)
async def user_locale(
    event: MessageEvent,
    db: AsyncSession,
    locale: Match[str | None],
    reset: bool,
) -> str:
    if event.guild is not None:
        guild_locale = await db.get(GuildLocale, (event.login.platform, event.guild.id))
        if guild_locale is not None and guild_locale.force:
            return L("locale_get_guild").format(lang=get_full_name(guild_locale.locale))
    user_locale = await db.get(UserLocale, (event.login.platform, event.user.id))
    if reset:
        if user_locale:
            await db.delete(user_locale)
            await db.commit()
            USER_LOCALES[event.login.platform, event.user.id] = None
        return L("locale_set_reset")
    l = locale.result
    if l is None:
        if user_locale is None:
            message = L("locale_get_unset")
        else:
            message = L("locale_get").format(lang=get_full_name(user_locale.locale))
        langs_header = LANG_SWITCH_HEADER.format(command=f"{COMMAND_PREFIX}lang")
        langs = format_langs()
        return f"{message}\n{langs_header}\n{langs}"
    if l not in lang.locales:
        return L("locale_set_invalid").format(lang=l)
    if user_locale is None:
        user_locale = UserLocale(
            platform=event.login.platform,
            user_id=event.user.id,
            locale=l,
        )
    else:
        user_locale.locale = l
    db.add(user_locale)
    await db.commit()
    USER_LOCALES[event.login.platform, event.user.id] = l
    return L("locale_set", l).format(lang=get_full_name(l))


@command.on(
    Alconna(
        "glang",
        Args["locale?", str, None],
        Option("--reset", action=store_true, dest="reset", default=False),
        Option("--force", action=store_true, dest="force", default=False),
        meta=CommandMeta("Get or set guild locale."),
    ),
)
@letoderea.propagate(
    require_permission("idhagnbot.i18n.glang", default_available=False, prompt=True),
)
@enter_if(lambda event: bool(event.guild))
async def guild_locale(
    event: MessageEvent,
    db: AsyncSession,
    locale: Match[str | None],
    reset: bool,
    force: bool,
) -> str:
    assert event.guild
    guild_locale = await db.get(GuildLocale, (event.login.platform, event.guild.id))
    if reset:
        if guild_locale:
            await db.delete(guild_locale)
            await db.commit()
            GUILD_LOCALES[event.login.platform, event.guild.id] = None
        return L("locale_set_reset")
    l = locale.result
    if l is None:
        if guild_locale is None:
            message = L("locale_get_unset")
        else:
            message = L("locale_get_force" if guild_locale.force else "locale_get")
            message = message.format(lang=get_full_name(guild_locale.locale))
        langs_header = LANG_SWITCH_HEADER.format(command=f"{COMMAND_PREFIX}glang")
        langs = format_langs()
        return f"{message}\n{langs_header}\n{langs}"
    if l not in lang.locales:
        return L("locale_set_invalid").format(lang=l)
    if guild_locale is None:
        guild_locale = GuildLocale(
            platform=event.login.platform,
            guild_id=event.guild.id,
            locale=l,
            force=force,
        )
    else:
        guild_locale.locale = l
        guild_locale.force = force
    db.add(guild_locale)
    await db.commit()
    GUILD_LOCALES[event.login.platform, event.guild.id] = (l, force)
    message = L("locale_set_force" if force else "locale_set", l)
    return message.format(lang=get_full_name(l))


system.pre_assign(
    AUTH_3,
    "idhagnbot.i18n.glang",
    Permission.VISIT | Permission.AVAILABLE,
)
system.pre_assign(
    ADMIN,
    "idhagnbot.i18n.glang",
    Permission.VISIT | Permission.AVAILABLE,
)
