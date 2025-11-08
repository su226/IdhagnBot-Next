import nonebot
from nonebot.adapters import Bot
from nonebot.exception import ActionFailed
from nonebot.message import event_preprocessor
from pydantic import BaseModel

from idhagnbot.config import SharedConfig
from idhagnbot.context import SceneIdRaw, get_target_id
from idhagnbot.hook import on_message_send_failed, on_message_sending, on_message_sent
from idhagnbot.message import MergedEvent, OrigMergedMsg
from idhagnbot.permission import permission
from idhagnbot.plugins.repeat.common import (
  CONDITION_REGISTRY,
  HANDLER_REGISTRY,
  LastMessage,
  already_counted,
  count_send,
  is_same,
  last_messages,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, Target, UniMessage

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


class Config(BaseModel):
  repeat_every: int = 2
  max_repeat: int = 1


CONFIG = SharedConfig("repeat", Config)


@event_preprocessor
async def _(bot: Bot, scene_id: SceneIdRaw, message: OrigMergedMsg) -> None:
  if already_counted.get():
    return
  last = last_messages.get(scene_id)
  if last and is_same(bot.adapter.get_name(), message, last.message):
    last_messages[scene_id] = LastMessage(
      message=message,
      received_count=last.received_count + 1,
      sending_count=last.sending_count,
      sent_count=last.sent_count,
    )
  else:
    last_messages[scene_id] = LastMessage(
      message=message,
      received_count=1,
      sending_count=0,
      sent_count=0,
    )


@on_message_sending
async def _(bot: Bot, message: UniMessage[Segment], target: Target) -> None:
  if already_counted.get():
    return
  scene_id = await get_target_id(target)
  last = last_messages.get(scene_id)
  if last and is_same(bot.adapter.get_name(), message, last.message):
    last_messages[scene_id] = LastMessage(
      message=message,
      received_count=last.received_count,
      sending_count=last.sending_count + 1,
      sent_count=last.sent_count,
    )


@on_message_sent
async def _(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
  message_ids: list[str],
) -> None:
  if already_counted.get():
    return
  scene_id = await get_target_id(target)
  last = last_messages.get(scene_id)
  if last and is_same(bot.adapter.get_name(), message, last.message):
    last_messages[scene_id] = LastMessage(
      message=message,
      received_count=last.received_count,
      sending_count=max(last.sending_count - 1, 0),
      sent_count=last.sent_count + 1,
    )
  else:
    last_messages[scene_id] = LastMessage(
      message=message,
      received_count=0,
      sending_count=0,
      sent_count=1,
    )


@on_message_send_failed
async def _(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
  e: Exception,
) -> None:
  if already_counted.get():
    return
  scene_id = await get_target_id(target)
  last = last_messages.get(scene_id)
  if last and is_same(bot.adapter.get_name(), message, last.message):
    last_messages[scene_id] = LastMessage(
      message=message,
      received_count=last.received_count,
      sending_count=max(last.sending_count - 1, 0),
      sent_count=last.sent_count,
    )


def is_command_like(message: UniMessage[Segment]) -> bool:
  return message.extract_plain_text().startswith(
    tuple(prefix for prefix in nonebot.get_driver().config.command_start if prefix),
  )


def check_condition(adapter: str, message: UniMessage[Segment]) -> bool:
  if condition := CONDITION_REGISTRY.get(adapter):
    return condition(message)
  return True


async def can_repeat(bot: Bot, scene_id: SceneIdRaw, message: OrigMergedMsg) -> bool:
  if (
    (last := last_messages.get(scene_id))
    and is_same(bot.adapter.get_name(), last.message, message)
    and not is_command_like(message)
    and check_condition(bot.adapter.get_name(), message)
  ):
    config = CONFIG()
    send_count = last.sent_count + last.sending_count
    if send_count < last.received_count // config.repeat_every and send_count < config.max_repeat:
      return True
  return False


repeat = nonebot.on_message(can_repeat, permission("repeat"))


@repeat.handle()
async def _(bot: Bot, events: MergedEvent, message: OrigMergedMsg, scene_id: SceneIdRaw) -> None:
  try:
    if handler := HANDLER_REGISTRY.get(bot.adapter.get_name()):
      await handler(bot, events, message, scene_id)
    else:
      with count_send(bot.adapter.get_name(), scene_id, message):
        await message.send()
  except ActionFailed:
    pass
