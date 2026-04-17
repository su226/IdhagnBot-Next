import re
from collections.abc import Sequence

import nonebot
from nonebot.adapters.discord import Bot, MessageComponentInteractionEvent
from nonebot.adapters.discord.api import (
  ActionRow,
  Button,
  ButtonStyle,
  DirectComponent,
  InteractionCallbackMessage,
  InteractionCallbackType,
  InteractionResponse,
  Snowflake,
)
from nonebot.exception import ActionFailed
from nonebot.typing import T_State

from idhagnbot.context import SceneId
from idhagnbot.help import CategoryItem, L
from idhagnbot.permission import Roles
from idhagnbot.plugins.help.common import HELP_PAGE_RE, get_context, join_path, normalize_path

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import QryItrface, Uninfo


async def interaction_edit_message(
  bot: Bot,
  event: MessageComponentInteractionEvent,
  content: str,
  components: Sequence[DirectComponent] | None = None,
) -> None:
  try:
    await bot.create_interaction_response(
      interaction_id=event.id,
      interaction_token=event.token,
      response=InteractionResponse(
        type=InteractionCallbackType.UPDATE_MESSAGE,
        data=InteractionCallbackMessage(
          content=content,
          components=list(components) if components else None,
        ),
      ),
    )
  except ActionFailed:
    assert isinstance(event.channel_id, Snowflake)
    await bot.edit_message(
      channel_id=event.channel_id,
      message_id=event.message.id,
      content=content,
      components=list(components) if components else None,
    )


async def check_help_page(event: MessageComponentInteractionEvent, state: T_State) -> bool:
  if match := HELP_PAGE_RE.match(event.data.custom_id):
    state["path"] = normalize_path(match["path"])
    state["page"] = int(match["page"])
    return True
  return False


def escape(string: str) -> str:
  return re.sub(r"([\\\*_`~])", r"\\\1", string)


help_page = nonebot.on_notice(check_help_page)


@help_page.handle()
async def handle_help_page(
  *,
  bot: Bot,
  event: MessageComponentInteractionEvent,
  session: Uninfo,
  interface: QryItrface,
  scene: SceneId,
  roles: Roles,
  state: T_State,
) -> None:
  context = await get_context(scene, session, interface, roles)
  page = state["page"]
  path = state["path"]
  try:
    category = CategoryItem.find(path, ctx=context)
  except (KeyError, ValueError):
    await interaction_edit_message(bot, event, L("not_available"))
    return
  content, page, total_pages = category.format_page(page, context)
  row = ActionRow(components=[])
  if page - 1 >= 0:
    row.components.append(
      Button(style=ButtonStyle.Primary, label="<", custom_id=f"help_{join_path(path)}_{page - 1}"),
    )
  if page + 1 < total_pages:
    row.components.append(
      Button(style=ButtonStyle.Primary, label=">", custom_id=f"help_{join_path(path)}_{page + 1}"),
    )
  await interaction_edit_message(bot, event, escape(content), [row])
