import re

import nonebot
from nonebot.adapters.telegram import Bot
from nonebot.adapters.telegram.event import CallbackQueryEvent
from nonebot.adapters.telegram.model import InlineKeyboardButton, InlineKeyboardMarkup
from nonebot.typing import T_State

from idhagnbot.context import SceneId
from idhagnbot.help import CategoryItem
from idhagnbot.permission import Roles
from idhagnbot.plugins.help.common import get_show_data, join_path, normalize_path

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import QryItrface, Uninfo

HELP_PAGE_RE = re.compile(r"help_(?P<path>.+)_(?P<page>\d+)")


def check_help_page(event: CallbackQueryEvent, state: T_State) -> bool:
  if event.data and (match := HELP_PAGE_RE.match(event.data)):
    state["path"] = normalize_path(match["path"])
    state["page"] = int(match["page"])
    return True
  return False


help_page = nonebot.on("inline", check_help_page)


@help_page.handle()
async def handle_help_page(*,
  bot: Bot,
  event: CallbackQueryEvent,
  session: Uninfo,
  interface: QryItrface,
  scene: SceneId,
  roles: Roles,
  state: T_State,
) -> None:
  if not event.message:
    return
  show_data = await get_show_data(scene, session, interface, roles)
  page = state["page"]
  path = state["path"]
  try:
    category = CategoryItem.find(path, check=show_data)
  except (KeyError, ValueError):
    await bot.edit_message_text(
      "无此条目或分类、权限不足或在当前上下文不可用",
      chat_id=event.message.chat.id,
      message_id=event.message.message_id,
    )
    await bot.answer_callback_query(event.id)
    return
  content, page, total_pages = category.format_page(show_data, [], page)
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
