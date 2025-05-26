import asyncio
from enum import Enum

import nonebot

from idhagnbot.help import ShowData

nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import Interface, SceneType, Session


async def get_available_groups(session: Session, interface: Interface, user_id: str) -> list[str]:
  async def in_group(group_id: str) -> bool:
    return bool(await interface.get_member(SceneType.GROUP, group_id, user_id))

  groups = await interface.get_scenes(SceneType.GROUP)
  results = await asyncio.gather(*(in_group(group.id) for group in groups))
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  return [f"{scope}:group:{group.id}" for group, result in zip(groups, results) if result]


async def get_show_data(
  scene: str,
  session: Session,
  interface: Interface,
  sorted_roles: list[str],
) -> ShowData:
  available_scenes = {scene}
  if session.scene.type == SceneType.PRIVATE:
    available_scenes.update(await get_available_groups(session, interface, session.user.id))
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  return ShowData(
    scope,
    f"{scope}:{session.user.id}",
    scene,
    available_scenes,
    session.scene.type == SceneType.PRIVATE,
    sorted_roles,
  )


def normalize_path(*path: str) -> list[str]:
  result: list[str] = []
  for i in path:
    result.extend(x for x in i.split(".") if x)
  return result


def join_path(path: list[str]) -> str:
  if not path:
    return "."
  return ".".join(path)
