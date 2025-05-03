import re
from datetime import datetime
from enum import Enum
from typing import Annotated

import nonebot
from nonebot.params import Depends
from pydantic import BaseModel, Field

from idhagnbot.config import SharedData
from idhagnbot.permission import CHANNEL_TYPES

nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import SceneType, Uninfo


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


def get_scene_id(session: Uninfo) -> str:
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  if session.scene.type == SceneType.PRIVATE:
    data = DATA().contexts.get(f"{scope}:{session.user.id}")
    return data.scene if data else f"{scope}:private:{session.scene.id}"
  if session.scene.type == SceneType.GROUP:
    return f"{scope}:group:{session.scene.id}"
  if session.scene.type in CHANNEL_TYPES and session.scene.parent:
    return f"{scope}:guild:{session.scene.parent.id}:channel:{session.scene.id}"
  raise ValueError("无法获取场景")


SceneId = Annotated[str, Depends(get_scene_id)]


def in_scene(scene_id: str, scene_ids: set[str]) -> bool:
  if scene_id in scene_ids:
    return True
  if PRIVATE in scene_ids and PRIVATE_RE.match(scene_id):
    return True
  if GROUP in scene_ids and GROUP_RE.match(scene_id):
    return True
  return GUILD in scene_ids and bool(GUILD_RE.match(scene_id))
