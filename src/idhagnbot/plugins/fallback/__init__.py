import re
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, ClassVar, Literal, TypeVar

import nonebot
from aiohttp import ClientError
from anyio.to_thread import run_sync
from nonebot.adapters import Bot, Event
from nonebot.consts import PREFIX_KEY
from nonebot.exception import ActionFailed
from nonebot.message import event_postprocessor, run_postprocessor, run_preprocessor
from nonebot.typing import T_State
from PIL import Image
from pydantic import BaseModel, Field, PrivateAttr, RootModel
from pygtrie import Trie  # pyright: ignore[reportMissingTypeStubs]
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.command import CommandBuilder
from idhagnbot.config import SharedConfig
from idhagnbot.context import SceneId, SceneIdRaw
from idhagnbot.help import COMMAND_PREFIX
from idhagnbot.image import paste, to_segment
from idhagnbot.message import UniMsg
from idhagnbot.permission import ADMINISTRATOR_OR_ABOVE
from idhagnbot.text import escape, render
from idhagnbot.third_party.bilibili_auth import ApiError

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, Text, UniMessage, on_alconna
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
  show_invaild_command: EnableSet = EnableSet.true()
  show_im_bot: EnableSet = EnableSet.true()
  show_exception: EnableSet = EnableSet.true()
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
    return "网络错误\n可能是命令使用的在线 API 不稳定，或者机器人服务器的网络问题。"
  if isinstance(exception, ManualException):
    return "管理员手动触发\n如果你不是群管理员，可以忽略这个。"
  if isinstance(exception, Image.DecompressionBombError):
    return "图片过大\n发送的图片或链接中的图片过大。"
  if isinstance(exception, ApiError):
    return "B站 API 异常\n接口出现更变或者被B站风控。"
  return None


def starts_with_command_prefix(message: UniMsg) -> bool:
  segment = message[0]
  if not isinstance(segment, Text):
    return False
  return any(segment.text.startswith(prefix) for prefix in DRIVER.config.command_start if prefix)


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
      reason = "未知错误\n这可能是 IdhagnBot Next 的设计缺陷，请向开发者寻求帮助。"

    header_markup = (
      "<span weight='heavy' size='200%'>这个要慌，问题很大</span>\n"
      "<span color='#ffffff88'>Something really bad happens. Panic!</span>"
    )
    content_markup = (
      "<b>IdhagnBot Next 遇到了一个内部错误。</b>\n"
      f"<span color='#f5f543'>可能原因: </span>{escape(reason)}"
    )
    content_fallback = f"IdhagnBot Next 遇到了一个内部错误。\n可能原因: {reason}"
    if session.scene.type != SceneType.PRIVATE:
      content_markup += (
        "\n<span color='#29b8db'>提示: </span>"
        f"群管理员可以发送 {COMMAND_PREFIX}suppress true 暂时禁用本群错误消息。"
      )
      content_fallback += (
        f"\n提示: 群管理员可以发送 {COMMAND_PREFIX}suppress true 暂时禁用本群错误消息。"
      )

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
      paste(im, header, (im.width // 2, 32), anchor="mt")
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
  if starts_with_command_prefix(message) and config.show_invaild_command[scene_id]:
    await UniMessage(Text("命令不存在、权限不足或不适用于当前上下文")).send(event, bot)
  if (
    event.is_tome()
    and config.show_im_bot[scene_id]
    and user_id
    and not await is_im_bot_suppressed_for(scope, user_id)
  ):
    await UniMessage(
      Text(
        f"本帐号为机器人，请发送 {COMMAND_PREFIX}帮助 查看可用命令（可以不@）\n"
        f"发送 {COMMAND_PREFIX}禁用提示 为你禁用本提示",
      ),
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
    await suppress_im_bot.finish("你已恢复“本帐号为机器人”的提示。")
  sql.add(ImBotSuppressedUser(platform=scope, user_id=user_id))
  await sql.commit()
  await suppress_im_bot.finish(
    f"你已禁用“本帐号为机器人”的提示，再次发送 {COMMAND_PREFIX}禁用提示 可恢复。",
  )


suppress_exception = (
  CommandBuilder()
  .node("fallback.suppress_exception")
  .parser(
    Alconna(
      "suppress",
      Args["toggle?", str, ""],
      meta=CommandMeta("暂时禁用错误消息"),
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
    await suppress_exception.finish("本群错误消息已禁用 24 小时。")
  elif toggle in ("false", "f", "0", "no", "n", "off"):
    info = await sql.get(ExceptionSuppressedScene, scene_id)
    if info:
      await sql.delete(info)
      await sql.commit()
    await suppress_exception.finish("本群错误消息已恢复。")
  else:
    await suppress_exception.finish(
      f"{COMMAND_PREFIX}suppress true - 暂时禁用本群错误消息。\n"
      f"{COMMAND_PREFIX}suppress false - 恢复本群错误消息。",
    )


raise_exception = (
  CommandBuilder()
  .node("fallback.raise_exception")
  .parser(
    Alconna(
      "raise",
      Args["confirm?", Literal["confirm"], None],
      meta=CommandMeta("手动触发一个错误"),
    ),
  )
  .default_grant_to(ADMINISTRATOR_OR_ABOVE)
  .build()
)


@raise_exception.handle()
async def _(confirm: Literal["confirm"] | None) -> None:
  if confirm == "confirm":
    raise ManualException
  await raise_exception.finish(f"{COMMAND_PREFIX}raise confirm - 手动触发一个错误")
