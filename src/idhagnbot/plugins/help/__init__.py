from enum import Enum
from typing import Optional

import nonebot

from idhagnbot.command import CommandBuilder
from idhagnbot.context import SceneId
from idhagnbot.help import CategoryItem, CommandItem, ShowData
from idhagnbot.permission import SortedRoles
from idhagnbot.plugins.help.common import get_available_groups, join_path, normalize_path

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, Match, MultiVar
from nonebot_plugin_alconna.uniseg import (
  At,
  Button,
  CustomNode,
  Reference,
  Segment,
  Text,
  UniMessage,
)
from nonebot_plugin_uninfo import QryItrface, SceneType, SupportAdapter, Uninfo

try:
  import idhagnbot.plugins.help.telegram as _
except ImportError:
  pass


def find_command(name: str) -> Optional[CommandItem]:
  try:
    return CommandItem.find(name)
  except KeyError:
    pass
  if name.startswith("/"):
    try:
      return CommandItem.find(name[1:])
    except KeyError:
      pass
  return None


help_ = (
  CommandBuilder()
  .node("help")
  .parser(
    Alconna(
      "帮助",
      Args["path", MultiVar(str, "*")],
      Args["page", int, 1],
      meta=CommandMeta("查看所有帮助"),
    ),
  )
  .aliases({"help"})
  .build()
)


@help_.handle()
async def handle_help(
  session: Uninfo,
  interface: QryItrface,
  scene: SceneId,
  sorted_roles: SortedRoles,
  path: Match[tuple[str]],
  page: Match[int],
) -> None:
  available_scenes = {scene}
  if session.scene.type == SceneType.PRIVATE:
    available_scenes.update(await get_available_groups(session, interface, session.user.id))
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  show_data = ShowData(
    scope,
    f"{scope}:{session.user.id}",
    scene,
    available_scenes,
    session.scene.type == SceneType.PRIVATE,
    sorted_roles,
  )
  if (
    len(path.result) == 1
    and (command := find_command(path.result[0]))
    and command.can_show(show_data)
  ):
    await help_.finish(command.format())
  normalized_path = normalize_path(*path.result)
  if len(normalized_path) == 0:
    category = CategoryItem.ROOT
    if not category.can_show(show_data):
      await help_.finish("无此条目或分类、权限不足或在当前上下文不可用")
  else:
    try:
      category = CategoryItem.find(normalized_path, check=show_data)
    except (KeyError, ValueError):
      await help_.finish("无此条目或分类、权限不足或在当前上下文不可用")
  if session.adapter == SupportAdapter.onebot11:
    pages = category.format_all(show_data, normalized_path)
    if len(pages) == 1:
      await help_.finish(pages[0])
    bot_info = await interface.get_member(session.scene.type, session.scene.id, session.self_id)
    if bot_info:
      bot_name = bot_info.nick or bot_info.user.nick or bot_info.user.name or "IdhagnBot"
    else:
      bot_name = "IdhagnBot"
    await help_.finish(
      Reference(nodes=[CustomNode(session.self_id, bot_name, [Text(page)]) for page in pages]),
    )
  content, page_id, total_pages = category.format_page(show_data, normalized_path, page.result - 1)
  message = UniMessage[Segment]([Text(content)])
  if page_id - 1 >= 0:
    value = f"help_{join_path(normalized_path)}_{page_id - 1}"
    message.append(Button("action", "<", id=value, permission=[At("user", session.user.id)]))
  if page_id + 1 < total_pages:
    value = f"help_{join_path(normalized_path)}_{page_id + 1}"
    message.append(Button("action", ">", id=value, permission=[At("user", session.user.id)]))
  await help_.finish(message)
