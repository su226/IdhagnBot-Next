import re
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, ClassVar, Literal, TypeVar

import nonebot
from aiohttp import ClientError
from anyio.to_thread import run_sync
from arclet.alconna._internal._util import levenshtein
from nonebot.adapters import Bot, Event
from nonebot.consts import PREFIX_KEY
from nonebot.exception import ActionFailed
from nonebot.message import event_postprocessor, run_postprocessor, run_preprocessor
from nonebot.typing import T_State
from PIL import Image
from pydantic import BaseModel, Field, PrivateAttr, RootModel
from pygtrie import Trie  # pyright: ignore[reportMissingTypeStubs]
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.command import COMMAND_LIKE_KEY, CommandBuilder
from idhagnbot.config import SharedConfig
from idhagnbot.context import SceneId, SceneIdRaw
from idhagnbot.help import COMMAND_PREFIX, CommandItem, Context
from idhagnbot.i18n import Locale, bound_lang
from idhagnbot.image import paste, to_segment
from idhagnbot.message import UniMsg
from idhagnbot.permission import ADMINISTRATOR_OR_ABOVE, Roles
from idhagnbot.text import escape, render
from idhagnbot.third_party.bilibili_auth import ApiError

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import (
  Alconna,
  Args,
  CommandMeta,
  Text,
  UniMessage,
  on_alconna,
)
from nonebot_plugin_alconna import Image as ImageSeg
from nonebot_plugin_orm import Model, async_scoped_session, get_session
from nonebot_plugin_uninfo import SceneType, Uninfo


class IncludeExcludeSet(BaseModel):
  include: list[re.Pattern[str]] = Field(default_factory=list)
  exclude: list[re.Pattern[str]] = Field(default_factory=list)


class EnableSet(RootModel[IncludeExcludeSet | bool]):
  def __getitem__(self, scene_id: str) -> bool:
    if isinstance(self.root, IncludeExcludeSet):
      if self.root.include and not any(pattern.search(scene_id) for pattern in self.root.include):
        return False
      return not any(pattern.search(scene_id) for pattern in self.root.exclude)
    return self.root

  @classmethod
  def false(cls) -> Any:
    return Field(default_factory=lambda: EnableSet(root=False))

  @classmethod
  def true(cls) -> Any:
    return Field(default_factory=lambda: EnableSet(root=True))


class Config(BaseModel):
  show_invalid_command: EnableSet = EnableSet.true()
  show_im_bot: EnableSet = EnableSet.true()
  show_exception: EnableSet = EnableSet.true()
  min_similarity: None | float = 0.6
  ignore_prefix_global: dict[str, set[str]] = Field(default_factory=dict)
  _ignore_prefix_global: dict[str, Trie] = PrivateAttr()
  ignore_prefix_local: dict[str, set[str]] = Field(default_factory=dict)
  _ignore_prefix_local: dict[str, Trie] = PrivateAttr()
  ignore_user: set[str] = Field(default_factory=set)

  def __init__(self, **data: Any) -> None:
    super().__init__(**data)
    self._ignore_prefix_global = {}
    for platform, prefixes in self.ignore_prefix_global.items():
      self._ignore_prefix_global[platform] = Trie((x, None) for x in prefixes)
    self._ignore_prefix_local = {}
    for scene_id, prefixes in self.ignore_prefix_local.items():
      self._ignore_prefix_local[scene_id] = Trie((x, None) for x in prefixes)

  def is_ignored_user(self, platform: str, user_id: str) -> bool:
    return f"{platform}:{user_id}" in self.ignore_user

  def has_ignored_prefix(self, scene_id: str, message: UniMsg) -> bool:
    segment = message[0]
    platform = scene_id.split(":", 1)[0]
    return isinstance(segment, Text) and (
      (
        platform in self.ignore_prefix_global
        and bool(self._ignore_prefix_global[platform].shortest_prefix(segment.text))
      )
      or (
        scene_id in self.ignore_prefix_local
        and bool(self._ignore_prefix_local[scene_id].shortest_prefix(segment.text))
      )
    )


class ImBotSuppressedUser(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_fallback_im_bot_suppressed_user"
  platform: Mapped[str] = mapped_column(primary_key=True)
  user_id: Mapped[str] = mapped_column(primary_key=True)


class ExceptionSuppressedScene(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_fallback_exception_suppressed_scene"
  scene_id: Mapped[str] = mapped_column(primary_key=True)
  until: Mapped[datetime]


async def is_exception_suppressed_in(scene_id: str) -> bool:
  async with get_session() as session:
    info = await session.get(ExceptionSuppressedScene, scene_id)
    if info and info.until > datetime.now():
      return True
  return False


async def is_im_bot_suppressed_for(platform: str, user_id: str) -> bool:
  async with get_session() as session:
    return bool(await session.get(ImBotSuppressedUser, (platform, user_id)))


RUN_KEY = "_idhagnbot_run"
DRIVER = nonebot.get_driver()
CONFIG = SharedConfig("fallback", Config)
L = bound_lang("idhagnbot_fallback")
ExceptionExplain = Callable[[Exception], str | None]
TExceptionExplain = TypeVar("TExceptionExplain", bound=ExceptionExplain)
registered_exception_explains = list[ExceptionExplain]()


def register_exception_explain(explain: TExceptionExplain) -> TExceptionExplain:
  registered_exception_explains.append(explain)
  return explain


class ManualException(Exception):
  def __init__(self) -> None:
    super().__init__(f"管理员使用 {COMMAND_PREFIX}raise 手动触发了错误")


@register_exception_explain
def builtin_exception_explain(exception: Exception) -> str | None:
  if isinstance(exception, ClientError):
    return L("error_type_network")
  if isinstance(exception, ManualException):
    return L("error_type_manual")
  if isinstance(exception, Image.DecompressionBombError):
    return L("error_type_large_image")
  if isinstance(exception, ApiError):
    return L("error_type_bilibili")
  return None


@run_preprocessor
async def pre_run(state: T_State) -> None:
  state[PREFIX_KEY][RUN_KEY] = True


@run_postprocessor
async def post_run(
  bot: Bot,
  event: Event,
  e: Exception,
  session: Uninfo,
  scene_id: SceneIdRaw,
) -> None:
  config = CONFIG()
  if config.show_exception[scene_id] and not await is_exception_suppressed_in(scene_id):
    for checker in registered_exception_explains:
      reason = checker(e)
      if reason:
        break
    else:
      reason = L("error_type_unknown")

    header_markup = L("error_markup_header")
    content_markup = L("error_markup_content").format(reason=escape(reason))
    content_fallback = L("error_plain_content").format(reason=reason)
    if session.scene.type != SceneType.PRIVATE:
      content_markup += "\n" + L("error_markup_group").format(prefix=COMMAND_PREFIX)
      content_fallback += "\n" + L("error_plain_group").format(prefix=COMMAND_PREFIX)

    def make() -> ImageSeg:
      header = render(header_markup, "sans", 32, color=(255, 255, 255), align="m", markup=True)
      content = render(
        content_markup,
        "sans",
        32,
        color=(255, 255, 255),
        box=max(640, header.width),
        markup=True,
      )
      size = (max(header.width, content.width) + 64, header.height + content.height + 80)
      im = Image.new("RGB", size, (30, 30, 30))
      im.paste((205, 49, 49), (0, 32, im.width, 32 + header.height))
      paste(im, header, (im.width // 2, 32), (0.5, 0))
      im.paste(content, (32, 48 + header.height), content)
      return to_segment(im)

    try:
      await UniMessage(await run_sync(make)).send(event, bot)
    except ActionFailed:
      await UniMessage(content_fallback).send(event, bot)


@event_postprocessor
async def post_event(
  bot: Bot,
  event: Event,
  state: T_State,
  session: Uninfo,
  scene_id: SceneIdRaw,
  message: UniMsg,
  roles: Roles,
  locale: Locale,
) -> None:
  if RUN_KEY in state[PREFIX_KEY]:
    return
  config = CONFIG()
  try:
    user_id = event.get_user_id()
  except (NotImplementedError, ValueError):
    user_id = None
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  if user_id and config.is_ignored_user(scope, user_id):
    return
  if config.has_ignored_prefix(scene_id, message):
    return
  if (match := state.get(COMMAND_LIKE_KEY)) and config.show_invalid_command[scene_id]:
    fallback = L("bad_command", locale)
    if config.min_similarity is not None:
      prefix, suffix = match
      context = Context(
        scope,
        scene_id,
        {scene_id},  # TODO: available_scenes
        session.scene.type == SceneType.PRIVATE,
        roles,
      )
      command, similarity = max(
        (
          (command, levenshtein(command, suffix))
          for command, item in CommandItem.COMMANDS.items()
          if item.check(context)
        ),
        key=lambda x: x[1],
      )
      if similarity >= config.min_similarity:
        fallback += f"\n{L('bad_command_suggestion', locale)}{prefix}{command}"
    await UniMessage(Text(fallback)).send(event, bot)
  if (
    event.is_tome()
    and config.show_im_bot[scene_id]
    and user_id
    and not await is_im_bot_suppressed_for(scope, user_id)
  ):
    await UniMessage(
      Text(L("im_a_bot", locale).format(prefix=COMMAND_PREFIX)),
    ).send(event, bot)


async def check_disable_show_im_bot(event: Event, scene_id: SceneIdRaw) -> bool:
  try:
    event.get_user_id()
  except (ValueError, NotImplementedError):
    return False
  return CONFIG().show_im_bot[scene_id]


# 直接使用 on_alconna 是为了不显示在帮助里
suppress_im_bot = on_alconna(
  Alconna("禁用提示"),
  check_disable_show_im_bot,
  use_cmd_start=True,
)


@suppress_im_bot.handle()
async def _(
  event: Event,
  session: Uninfo,
  sql: async_scoped_session,
) -> None:
  user_id = event.get_user_id()
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  if ignored := await sql.get(ImBotSuppressedUser, (scope, user_id)):
    await sql.delete(ignored)
    await sql.commit()
    await suppress_im_bot.finish(L("im_a_bot_restored"))
  sql.add(ImBotSuppressedUser(platform=scope, user_id=user_id))
  await sql.commit()
  await suppress_im_bot.finish(L("im_a_bot_suppressed").format(prefix=COMMAND_PREFIX))


suppress_exception = (
  CommandBuilder()
  .node("fallback.suppress_exception")
  .parser(
    Alconna(
      "suppress",
      Args["toggle?", str, ""],
      meta=CommandMeta("__idhagnbot_fallback:command_brief_suppress_exception__"),
    ),
  )
  .default_grant_to(ADMINISTRATOR_OR_ABOVE)
  .build()
)


@suppress_exception.handle()
async def _(toggle: str, scene_id: SceneId, sql: async_scoped_session) -> None:
  toggle = toggle.lower()
  if toggle in ("true", "t", "1", "yes", "y", "on"):
    until = datetime.now() + timedelta(1)
    if info := await sql.get(ExceptionSuppressedScene, scene_id):
      info.until = until
      sql.add(info)
    else:
      sql.add(ExceptionSuppressedScene(scene_id=scene_id, until=until))
    await sql.commit()
    await suppress_exception.finish(L("error_suppressed"))
  elif toggle in ("false", "f", "0", "no", "n", "off"):
    info = await sql.get(ExceptionSuppressedScene, scene_id)
    if info:
      await sql.delete(info)
      await sql.commit()
    await suppress_exception.finish(L("error_restored"))
  else:
    await suppress_exception.finish(L("error_suppress_usage").format(prefix=COMMAND_PREFIX))


raise_exception = (
  CommandBuilder()
  .node("fallback.raise_exception")
  .parser(
    Alconna(
      "raise",
      Args["confirm?", Literal["confirm"], None],
      meta=CommandMeta("__idhagnbot_fallback:command_brief_raise_exception__"),
    ),
  )
  .default_grant_to(ADMINISTRATOR_OR_ABOVE)
  .build()
)


@raise_exception.handle()
async def _(confirm: Literal["confirm"] | None) -> None:
  if confirm == "confirm":
    raise ManualException
  await raise_exception.finish(L("error_raise_usage").format(prefix=COMMAND_PREFIX))
