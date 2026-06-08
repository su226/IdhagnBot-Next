import nonebot

from idhagnbot.command import CommandBuilder
from idhagnbot.context import BotAnyNick, SceneId
from idhagnbot.help import CategoryItem, CommandItem, L
from idhagnbot.permission import Roles
from idhagnbot.plugins.help.common import get_context, join_path, normalize_path

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
  import idhagnbot.plugins.help.discord
except ImportError:
  pass
try:
  import idhagnbot.plugins.help.satori
except ImportError:
  pass
try:
  import idhagnbot.plugins.help.telegram  # noqa: F401
except ImportError:
  pass


def find_command(name: str) -> CommandItem | None:
  try:
    return CommandItem.COMMANDS[name]
  except KeyError:
    pass
  for prefix in nonebot.get_driver().config.command_start:
    if prefix and name.startswith(prefix):
      try:
        return CommandItem.COMMANDS[name[len(prefix) :]]
      except KeyError:
        pass
  return None


help_ = (
  CommandBuilder()
  .node("help")
  .parser(
    Alconna(
      "help",
      Args["path", MultiVar(str, "*")],
      Args["page", int, 1],
      meta=CommandMeta("__idhagnbot_help:command_brief_help__"),
    ),
  )
  .aliases({"帮助": "zh-CN"})
  .build()
)


@help_.handle()
async def handle_help(
  *,
  session: Uninfo,
  interface: QryItrface,
  scene: SceneId,
  roles: Roles,
  path: tuple[str, ...],
  page: int,
  bot_nick: BotAnyNick,
) -> None:
  show_data = await get_context(scene, session, interface, roles)
  if len(path) == 1 and (command := find_command(path[0])) and command.check(show_data):
    await help_.finish(command.format_detail())
  normalized_path = normalize_path(*path)
  try:
    category = CategoryItem.find(normalized_path, ctx=show_data)
  except (KeyError, ValueError):
    await help_.finish(L("not_available"))
  if session.adapter == SupportAdapter.onebot11:
    pages = category.format_forward(show_data)
    if len(pages) == 1:
      await help_.finish(pages[0])
    await help_.finish(
      Reference(nodes=[CustomNode(session.self_id, bot_nick, [Text(page)]) for page in pages]),
    )
  content, page_id, total_pages = category.format_page(page - 1, show_data)
  message = UniMessage[Segment]([Text(content)])
  if page_id - 1 >= 0:
    value = f"help_{join_path(normalized_path)}_{page_id - 1}"
    message.append(Button("action", "<", id=value, permission=[At("user", session.user.id)]))
  if page_id + 1 < total_pages:
    value = f"help_{join_path(normalized_path)}_{page_id + 1}"
    message.append(Button("action", ">", id=value, permission=[At("user", session.user.id)]))
  await help_.finish(message)
