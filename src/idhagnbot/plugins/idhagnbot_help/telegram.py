import re
from enum import Enum

import nonebot
from nonebot.adapters.telegram import Bot
from nonebot.adapters.telegram.event import CallbackQueryEvent
from nonebot.adapters.telegram.model import InlineKeyboardButton, InlineKeyboardMarkup
from nonebot.typing import T_State

from idhagnbot.context import SceneId
from idhagnbot.help import CategoryItem, ShowData
from idhagnbot.permission import SortedRoles
from idhagnbot.plugins.idhagnbot_help.common import get_available_groups, join_path, normalize_path

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import QryItrface, SceneType, Uninfo

HELP_PAGE_RE = re.compile(r"help_(?P<path>.+)_(?P<page>\d+)")


def check_help_page(event: CallbackQueryEvent, state: T_State) -> bool:
  if event.data and (match := HELP_PAGE_RE.match(event.data)):
    state["path"] = normalize_path(match["path"])
    state["page"] = int(match["page"])
    return True
  return False


help_page = nonebot.on("inline", check_help_page)


@help_page.handle()
async def handle_help_page(
  bot: Bot,
  event: CallbackQueryEvent,
  session: Uninfo,
  interface: QryItrface,
  scene: SceneId,
  sorted_roles: SortedRoles,
  state: T_State,
) -> None:
  if not event.message:
    return
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
  page = state["page"]
  path = state["path"]
  content, page, total_pages = CategoryItem.ROOT.format_page(show_data, [], page)
  buttons = InlineKeyboardMarkup(inline_keyboard=[[]])
  if page - 1 >= 0:
    buttons.inline_keyboard[0].append(
      InlineKeyboardButton(text="<", callback_data=f"help_{join_path(path)}_{page - 1}"),
    )
  if page + 1 < total_pages:
    buttons.inline_keyboard[0].append(
      InlineKeyboardButton(text=">", callback_data=f"help_{join_path(path)}_{page + 1}"),
    )
  await bot.edit_message_text(
    content,
    chat_id=event.message.chat.id,
    message_id=event.message.message_id,
    reply_markup=buttons,
  )
  await bot.answer_callback_query(event.id)
