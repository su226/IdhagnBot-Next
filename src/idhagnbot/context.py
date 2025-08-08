import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

import nonebot
from nonebot.adapters import Bot
from nonebot.params import Depends
from pydantic import BaseModel, Field

from idhagnbot.config import SharedData
from idhagnbot.permission import CHANNEL_TYPES

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Target, get_bot
from nonebot_plugin_uninfo import Scene, SceneType, Uninfo, get_interface


class Context(BaseModel):
  scene: str
  expire: datetime


class Data(BaseModel):
  contexts: dict[str, Context] = Field(default_factory=dict)


DATA = SharedData("context", Data)
PRIVATE = "private"
NON_PRIVATE = "non_private"
GROUP = "group"
GUILD = "guild"
PRIVATE_RE = re.compile(r"^(?P<platform>[^:]+):private:(?P<private>[^:]+)$")
GROUP_RE = re.compile(r"^(?P<platform>[^:]+):group:(?P<group>[^:]+)$")
GUILD_RE = re.compile(r"^(?P<platform>[^:]+):guild:(?P<guild>[^:]+):channel:(?P<channel>[^:]+)$")


def get_scene_id_raw(session: Uninfo) -> str:
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  if session.scene.type == SceneType.PRIVATE:
    return f"{scope}:private:{session.scene.id}"
  if session.scene.type == SceneType.GROUP:
    return f"{scope}:group:{session.scene.id}"
  if session.scene.type in CHANNEL_TYPES and session.scene.parent:
    return f"{scope}:guild:{session.scene.parent.id}:channel:{session.scene.id}"
  raise ValueError("无法获取场景")


def get_scene_id(session: Uninfo) -> str:
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  if session.scene.type == SceneType.PRIVATE:
    data = DATA().contexts.get(f"{scope}:{session.user.id}")
    if data:
      return data.scene
  return get_scene_id_raw(session)


SceneIdRaw = Annotated[str, Depends(get_scene_id_raw)]
SceneId = Annotated[str, Depends(get_scene_id)]


async def get_target_id(target: Target) -> str:
  bot = await target.select()
  interface = get_interface(bot)
  assert interface
  scope = interface.basic_info()["scope"]._name_
  if target.channel:
    return f"{scope}:guild:{target.parent_id}:channel:{target.id}"
  if target.private:
    return f"{scope}:private:{target.id}"
  return f"{scope}:group:{target.id}"


def _uninfo_predicate(platform: str) -> Callable[[Bot], Awaitable[bool]]:
  async def predicate(bot: Bot) -> bool:
    interface = get_interface(bot)
    return bool(interface) and interface.basic_info()["scope"]._name_ == platform

  return predicate


def _uninfo_selector(platform: str) -> Callable[[Target, Bot], Awaitable[bool]]:
  async def predicate(target: Target, bot: Bot) -> bool:
    interface = get_interface(bot)
    return bool(interface) and interface.basic_info()["scope"]._name_ == platform

  return predicate


def get_target(scene_id: str) -> Target:
  if match := PRIVATE_RE.match(scene_id):
    return Target(match["private"], private=True, selector=_uninfo_selector(match["platform"]))
  if match := GROUP_RE.match(scene_id):
    return Target(match["group"], selector=_uninfo_selector(match["platform"]))
  if match := GUILD_RE.match(scene_id):
    return Target(
      match["channel"],
      match["guild"],
      channel=True,
      selector=_uninfo_selector(match["platform"]),
    )
  raise ValueError("无效场景 ID")


async def get_scene(scene_id: str) -> Optional[Scene]:
  if match := PRIVATE_RE.match(scene_id):
    bot = await get_bot(predicate=_uninfo_predicate(match["platform"]), rand=True)
    interface = get_interface(bot)
    assert interface
    scene = await interface.get_scene(SceneType.PRIVATE, match["private"])
  elif match := GROUP_RE.match(scene_id):
    bot = await get_bot(predicate=_uninfo_predicate(match["platform"]), rand=True)
    interface = get_interface(bot)
    assert interface
    scene = await interface.get_scene(SceneType.GROUP, match["group"])
  elif match := GUILD_RE.match(scene_id):
    bot = await get_bot(predicate=_uninfo_predicate(match["platform"]), rand=True)
    interface = get_interface(bot)
    assert interface
    scene = await interface.get_scene(
      SceneType.CHANNEL_TEXT,
      match["channel"],
      parent_scene_id=match["guild"],
    )
  else:
    raise ValueError("无效场景 ID")
  return scene


def in_scene(scene_id: str, scene_ids: set[str]) -> bool:
  if scene_id in scene_ids:
    return True
  if PRIVATE in scene_ids and PRIVATE_RE.match(scene_id):
    return True
  if GROUP in scene_ids and GROUP_RE.match(scene_id):
    return True
  return GUILD in scene_ids and bool(GUILD_RE.match(scene_id))
