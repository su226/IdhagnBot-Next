import nonebot
from nonebot.adapters.satori import Bot
from nonebot.adapters.satori.event import InteractionButtonEvent
from nonebot.adapters.satori.message import Message, MessageSegment
from nonebot.typing import T_State

from idhagnbot.context import SceneId
from idhagnbot.help import CategoryItem
from idhagnbot.permission import Roles
from idhagnbot.plugins.help.common import HELP_PAGE_RE, get_show_data, join_path, normalize_path

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import QryItrface, Uninfo


def check_help_page(event: InteractionButtonEvent, state: T_State) -> bool:
  if event.button.id and (match := HELP_PAGE_RE.match(event.button.id)):
    state["path"] = normalize_path(match["path"])
    state["page"] = int(match["page"])
    return True
  return False


help_page = nonebot.on_notice(check_help_page)


@help_page.handle()
async def handle_help_page(
  *,
  bot: Bot,
  event: InteractionButtonEvent,
  session: Uninfo,
  interface: QryItrface,
  scene: SceneId,
  roles: Roles,
  state: T_State,
) -> None:
  if not event.message or not event.channel:
    return
  show_data = await get_show_data(scene, session, interface, roles)
  page = state["page"]
  path = state["path"]
  try:
    category = CategoryItem.find(path, check=show_data)
  except (KeyError, ValueError):
    await bot.message_update(
      channel_id=event.channel.id,
      message_id=event.message.id,
      content="无此条目或分类、权限不足或在当前上下文不可用",
    )
    return
  content, page, total_pages = category.format_page(show_data, path, page)
  message = Message(MessageSegment.text(content))
  if page - 1 >= 0:
    message.append(MessageSegment.action_button(f"help_{join_path(path)}_{page - 1}", "<"))
  if page + 1 < total_pages:
    message.append(MessageSegment.action_button(f"help_{join_path(path)}_{page + 1}", ">"))
  await bot.message_update(
    channel_id=event.channel.id,
    message_id=event.message.id,
    content=str(message),
  )
