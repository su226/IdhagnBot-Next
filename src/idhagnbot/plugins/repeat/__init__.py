from itertools import chain

import nonebot
from nonebot.adapters import Bot
from nonebot.exception import ActionFailed
from nonebot.message import event_preprocessor

from idhagnbot.command import COMMAND_LIKE_KEY, IDHAGNBOT_KEY
from idhagnbot.context import SceneIdRaw, get_target_id
from idhagnbot.hook import on_message_send_failed, on_message_sending, on_message_sent
from idhagnbot.hook.common import SentMessage
from idhagnbot.message import MergedEvent, OrigMergedMsg
from idhagnbot.permission import permission
from idhagnbot.plugins.repeat.common import (
  ALREADY_COUNTED,
  CONDITION_REGISTRY,
  CONFIG,
  HANDLER_REGISTRY,
  LastMessage,
  count_received,
  count_send,
  count_send_failed,
  count_sending,
  count_sent,
  is_same,
)

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
from nonebot.typing import T_State
from nonebot_plugin_alconna import Segment, Target, UniMessage
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_uninfo import SceneType, Uninfo

try:
  from idhagnbot.plugins.repeat.telegram import register
except ImportError:
  pass
else:
  register()

try:
  from idhagnbot.plugins.repeat.onebot import register
except ImportError:
  pass
else:
  register()

try:
  from idhagnbot.plugins.repeat.satori import register
except ImportError:
  pass
else:
  register()


@event_preprocessor
async def _(bot: Bot, scene_id: SceneIdRaw, message: OrigMergedMsg) -> None:
  if ALREADY_COUNTED.get():
    return
  await count_received(bot.adapter.get_name(), scene_id, message)


@on_message_sending
async def _(bot: Bot, message: UniMessage[Segment], target: Target) -> None:
  if ALREADY_COUNTED.get():
    return
  scene_id = await get_target_id(target)
  await count_sending(bot.adapter.get_name(), scene_id, message)


@on_message_sent
async def _(
  bot: Bot,
  original_message: UniMessage[Segment],
  messages: list[SentMessage],
  target: Target,
) -> None:
  if ALREADY_COUNTED.get():
    return
  scene_id = await get_target_id(target)
  message = UniMessage(chain.from_iterable(message.content for message in messages))
  await count_sent(bot.adapter.get_name(), scene_id, message)


@on_message_send_failed
async def _(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
  e: Exception,
) -> None:
  if ALREADY_COUNTED.get():
    return
  scene_id = await get_target_id(target)
  await count_send_failed(bot.adapter.get_name(), scene_id, message)


def is_ignored(scene_id: str, message: UniMessage[Segment]) -> bool:
  text = message.extract_plain_text()
  config = CONFIG()
  for pattern in config.global_ignore:
    if pattern.search(text):
      return True
  if patterns := config.local_ignore.get(scene_id):
    for pattern in patterns:
      if pattern.search(text):
        return True
  return False


def check_condition(adapter: str, message: UniMessage[Segment]) -> bool:
  if condition := CONDITION_REGISTRY.get(adapter):
    return condition(message)
  return True


async def can_repeat(
  bot: Bot,
  session: Uninfo,
  scene_id: SceneIdRaw,
  message: OrigMergedMsg,
  sql: async_scoped_session,
  state: T_State,
) -> bool:
  if (
    session.scene.type != SceneType.PRIVATE
    and not state[IDHAGNBOT_KEY][COMMAND_LIKE_KEY]
    and not is_ignored(scene_id, message)
    and check_condition(bot.adapter.get_name(), message)
    and (last := await sql.get(LastMessage, scene_id))
    and is_same(bot.adapter.get_name(), message, last)
  ):
    config = CONFIG()
    send_count = last.sent_count + last.sending_count
    if send_count < last.received_count // config.repeat_every and send_count < config.max_repeat:
      return True
  return False


repeat = nonebot.on_message(can_repeat, permission("repeat"))


@repeat.handle()
async def _(
  *,
  bot: Bot,
  events: MergedEvent,
  message: OrigMergedMsg,
  scene_id: SceneIdRaw,
) -> None:
  try:
    if handler := HANDLER_REGISTRY.get(bot.adapter.get_name()):
      await handler(bot, events, message, scene_id)
    else:
      async with count_send(bot.adapter.get_name(), scene_id, message):
        await message.send()
  except ActionFailed:
    pass
