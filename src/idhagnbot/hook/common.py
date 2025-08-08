from collections.abc import Awaitable, Callable

import anyio
import nonebot
from nonebot.adapters import Bot
from nonebot.typing import T_CalledAPIHook, T_CallingAPIHook

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, Target, UniMessage

MessageSendingHook = Callable[[Bot, UniMessage[Segment], Target], Awaitable[None]]
MessageSentHook = Callable[[Bot, UniMessage[Segment], Target, list[str]], Awaitable[None]]
MessageSendFailedHook = Callable[[Bot, UniMessage[Segment], Target, Exception], Awaitable[None]]
CALLING_API_REGISTRY = dict[str, T_CallingAPIHook]()
CALLED_API_REGISTRY = dict[str, T_CalledAPIHook]()
MESSAGE_SENDING_HOOKS = list[MessageSendingHook]()
MESSAGE_SENT_HOOKS = list[MessageSentHook]()
MESSAGE_SEND_FAILED_HOOKS = list[MessageSendFailedHook]()


async def call_message_sending_hook(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
) -> None:
  async with anyio.create_task_group() as tg:
    for hook in MESSAGE_SENDING_HOOKS:
      tg.start_soon(hook, bot, message, target)


async def call_message_sent_hook(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
  ids: list[str],
) -> None:
  async with anyio.create_task_group() as tg:
    for hook in MESSAGE_SENT_HOOKS:
      tg.start_soon(hook, bot, message, target, ids)


async def call_message_send_failed_hook(
  bot: Bot,
  message: UniMessage[Segment],
  target: Target,
  e: Exception,
) -> None:
  async with anyio.create_task_group() as tg:
    for hook in MESSAGE_SEND_FAILED_HOOKS:
      tg.start_soon(hook, bot, message, target, e)
