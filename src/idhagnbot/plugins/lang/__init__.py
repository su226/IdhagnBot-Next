from enum import Enum
from typing import Annotated, Any, ClassVar

import nonebot
from nonebot.message import event_preprocessor
from nonebot.params import Depends
from nonebot.typing import T_State
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from tarina import LRU

from idhagnbot.command import CommandBuilder
from idhagnbot.context import SceneId, SceneIdRaw
from idhagnbot.help import COMMAND_PREFIX
from idhagnbot.i18n import LOCALE_KEY, bound_lang, get_full_name, get_name, lang
from idhagnbot.permission import ADMINISTRATOR_OR_ABOVE

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, Option, store_true
from nonebot_plugin_orm import Model, async_scoped_session, get_session
from nonebot_plugin_uninfo import Uninfo


class UserLocale(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_lang_user_locale"
  platform: Mapped[str] = mapped_column(primary_key=True)
  user_id: Mapped[str] = mapped_column(primary_key=True)
  locale: Mapped[str]


class SceneLocale(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_lang_scene_locale"
  scene_id: Mapped[str] = mapped_column(primary_key=True)
  locale: Mapped[str]
  force: Mapped[bool]


# TypeError: type '_lru_c.LRU' is not subscriptable
USER_LOCALES: "LRU[tuple[str, str], str | None]" = LRU(128)
SCENE_LOCALES: "LRU[str, tuple[str, bool] | None]" = LRU(128)


async def query_scene_locale(sql: AsyncSession, scene_id: str) -> tuple[str, bool] | None:
  try:
    return SCENE_LOCALES[scene_id]
  except KeyError:
    pass
  locale_config = await sql.get(SceneLocale, scene_id)
  locale = None if locale_config is None else (locale_config.locale, locale_config.force)
  SCENE_LOCALES[scene_id] = locale
  return locale


async def query_user_locale(sql: AsyncSession, platform: str, user_id: str) -> str | None:
  try:
    return USER_LOCALES[platform, user_id]
  except KeyError:
    pass
  locale_config = await sql.get(UserLocale, (platform, user_id))
  locale = None if locale_config is None else locale_config.locale
  USER_LOCALES[platform, user_id] = locale
  return locale


async def query_locale(session: Uninfo, scene_id: SceneIdRaw) -> str | None:
  async with get_session() as sql:
    scene_locale = await query_scene_locale(sql, scene_id)
    if scene_locale is not None and scene_locale[1]:
      return scene_locale[0]
    scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
    user_locale = await query_user_locale(sql, scope, session.user.id)
    if user_locale is not None:
      return user_locale
    if scene_locale is not None:
      return scene_locale[0]
  return None


@event_preprocessor
async def _(locale: Annotated[str, Depends(query_locale)], state: T_State) -> None:
  state[LOCALE_KEY] = locale


def format_langs() -> str:
  return "\n".join(f"{key}: {get_name(key)}" for key in lang.locales)


L = bound_lang("idhagnbot_lang")
LANG_SWITCH_HEADER = (
  "Use {command} <ID> (not name) to switch locale.\nAvailable locales (ID: name):"
)


user_locale = (
  CommandBuilder()
  .node("lang.user_locale")
  .parser(
    Alconna(
      "lang",
      Args["locale?", str, None],
      Option("--reset", action=store_true, dest="reset", default=False),
      meta=CommandMeta("Get or set user locale."),
    ),
  )
  .build()
)


@user_locale.handle()
async def _(locale: str | None, reset: bool, session: Uninfo, sql: async_scoped_session) -> None:
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  locale_config = await sql.get(UserLocale, (scope, session.user.id))
  if reset:
    if locale_config:
      await sql.delete(locale_config)
      await sql.commit()
      USER_LOCALES[scope, session.user.id] = None
    await user_locale.finish(L("locale_set_reset"))
  if locale is None:
    if locale_config is None:
      message = L("locale_get_unset")
    else:
      message = L("locale_get").format(lang=get_full_name(locale_config.locale))
    langs_header = LANG_SWITCH_HEADER.format(command=f"{COMMAND_PREFIX}lang")
    langs = format_langs()
    await user_locale.finish(f"{message}\n{langs_header}\n{langs}")
  if locale not in lang.locales:
    await user_locale.finish(L("locale_set_invalid").format(lang=locale))
  if locale_config is None:
    locale_config = UserLocale(platform=scope, user_id=session.user.id, locale=locale)
  else:
    locale_config.locale = locale
  sql.add(locale_config)
  await sql.commit()
  USER_LOCALES[scope, session.user.id] = locale
  message = L("locale_set", locale)
  await user_locale.finish(message.format(lang=get_full_name(locale)))


scene_locale = (
  CommandBuilder()
  .node("lang.scene_locale")
  .parser(
    Alconna(
      "glang",
      Args["locale?", str, None],
      Option("--reset", action=store_true, dest="reset", default=False),
      Option("--force", action=store_true, dest="force", default=False),
      meta=CommandMeta("Get or set scene locale."),
    ),
  )
  .default_grant_to(ADMINISTRATOR_OR_ABOVE)
  .build()
)


@scene_locale.handle()
async def _(
  locale: str | None,
  reset: bool,
  force: bool,
  scene_id: SceneId,
  sql: async_scoped_session,
) -> None:
  locale_config = await sql.get(SceneLocale, scene_id)
  if reset:
    if locale_config:
      await sql.delete(locale_config)
      await sql.commit()
      SCENE_LOCALES[scene_id] = None
    await scene_locale.finish(L("locale_set_reset"))
  if locale is None:
    if locale_config is None:
      message = L("locale_get_unset")
    else:
      message = L("locale_get_force" if locale_config.force else "locale_get")
      message = message.format(lang=get_full_name(locale_config.locale))
    langs_header = LANG_SWITCH_HEADER.format(command=f"{COMMAND_PREFIX}glang")
    langs = langs_header + "\n" + format_langs()
    await scene_locale.finish(f"{message}\n{langs_header}\n{langs}")
  if locale not in lang.locales:
    await scene_locale.finish(L("locale_set_invalid").format(lang=locale))
  if locale_config is None:
    locale_config = SceneLocale(scene_id=scene_id, locale=locale, force=force)
  else:
    locale_config.locale = locale
    locale_config.force = force
  sql.add(locale_config)
  await sql.commit()
  SCENE_LOCALES[scene_id] = (locale, force)
  message = L("locale_set_force" if force else "locale_set", locale)
  await scene_locale.finish(message.format(lang=get_full_name(locale)))
