from collections.abc import Awaitable, Callable
from copy import copy
from typing import Any, TypeGuard, cast

import anyio
import nonebot
from nonebot import logger
from nonebot.adapters import Bot
from nonebot.typing import T_CalledAPIHook, T_CallingAPIHook

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, Target, UniMessage
from nonebot_plugin_alconna.uniseg.segment import Media

MessageSendingHook = Callable[[Bot, UniMessage[Segment], Target], Awaitable[None]]
MessageSentHook = Callable[[Bot, UniMessage[Segment], Target, list[str]], Awaitable[None]]
MessageSendFailedHook = Callable[[Bot, UniMessage[Segment], Target, Exception], Awaitable[None]]
CALLING_API_REGISTRY = dict[str, T_CallingAPIHook]()
CALLED_API_REGISTRY = dict[str, T_CalledAPIHook]()
MESSAGE_SENDING_HOOKS = list[MessageSendingHook]()
MESSAGE_SENT_HOOKS = list[MessageSentHook]()
MESSAGE_SEND_FAILED_HOOKS = list[MessageSendFailedHook]()


def is_raw_media(segment: Segment) -> TypeGuard[Media]:
  return isinstance(segment, Media) and bool(segment.raw)


def clean_message_for_logging(message: UniMessage[Segment]) -> UniMessage[Segment]:
  if any(is_raw_media(segment) for segment in message):
    message = copy(message)
    for i, segment in enumerate(message):
      if is_raw_media(segment):
        segment1 = copy(segment)
        segment1.raw = cast(Any, ...)
        message[i] = segment1
  return message


async def call_message_sending_hook(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
) -> None:
  logger.opt(colors=True).debug(
    "正在发送消息: <y>{!r}</y> <g>{}</g>",
    clean_message_for_logging(message),
    target,
  )
  async with anyio.create_task_group() as tg:
    for hook in MESSAGE_SENDING_HOOKS:
      tg.start_soon(hook, bot, message, target)


async def call_message_sent_hook(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
  ids: list[str],
) -> None:
  logger.opt(colors=True).debug(
    "已发送消息: <y>{!r}</y> <g>{}</g>",
    clean_message_for_logging(message),
    target,
  )
  async with anyio.create_task_group() as tg:
    for hook in MESSAGE_SENT_HOOKS:
      tg.start_soon(hook, bot, message, target, ids)


async def call_message_send_failed_hook(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
  e: Exception,
) -> None:
  logger.opt(colors=True).debug(
    "发送消息失败: <y>{!r}</y> <g>{}</g>",
    clean_message_for_logging(message),
    target,
  )
  async with anyio.create_task_group() as tg:
    for hook in MESSAGE_SEND_FAILED_HOOKS:
      tg.start_soon(hook, bot, message, target, e)
