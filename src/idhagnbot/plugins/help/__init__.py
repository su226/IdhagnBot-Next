from typing import Optional

import nonebot

from idhagnbot.command import CommandBuilder
from idhagnbot.context import BotAnyNick, SceneId
from idhagnbot.help import CategoryItem, CommandItem
from idhagnbot.permission import Roles
from idhagnbot.plugins.help.common import get_show_data, join_path, normalize_path

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, MultiVar
from nonebot_plugin_alconna.uniseg import (
  At,
  Button,
  CustomNode,
  Reference,
  Segment,
  Text,
  UniMessage,
)
from nonebot_plugin_uninfo import QryItrface, SupportAdapter, Uninfo

try:
  import idhagnbot.plugins.help.telegram as _
except ImportError:
  pass
try:
  import idhagnbot.plugins.help.satori as _
except ImportError:
  pass


def find_command(name: str) -> Optional[CommandItem]:
  try:
    return CommandItem.find(name)
  except KeyError:
    pass
  for prefix in nonebot.get_driver().config.command_start:
    if name.startswith(prefix):
      try:
        return CommandItem.find(name[len(prefix) :])
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
  roles: Roles,
  path: tuple[str, ...],
  page: int,
  bot_nick: BotAnyNick,
) -> None:
  show_data = await get_show_data(scene, session, interface, roles)
  if len(path) == 1 and (command := find_command(path[0])) and command.can_show(show_data):
    await help_.finish(command.format())
  normalized_path = normalize_path(*path)
  try:
    category = CategoryItem.find(normalized_path, check=show_data)
  except (KeyError, ValueError):
    await help_.finish("无此条目或分类、权限不足或在当前上下文不可用")
  if session.adapter == SupportAdapter.onebot11:
    pages = category.format_all(show_data, normalized_path)
    if len(pages) == 1:
      await help_.finish(pages[0])
    await help_.finish(
      Reference(nodes=[CustomNode(session.self_id, bot_nick, [Text(page)]) for page in pages]),
    )
  content, page_id, total_pages = category.format_page(show_data, normalized_path, page - 1)
  message = UniMessage[Segment]([Text(content)])
  if page_id - 1 >= 0:
    value = f"help_{join_path(normalized_path)}_{page_id - 1}"
    message.append(Button("action", "<", id=value, permission=[At("user", session.user.id)]))
  if page_id + 1 < total_pages:
    value = f"help_{join_path(normalized_path)}_{page_id + 1}"
    message.append(Button("action", ">", id=value, permission=[At("user", session.user.id)]))
  await help_.finish(message)
