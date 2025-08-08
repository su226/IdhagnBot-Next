from typing import Any, Optional, TypeVar

from nonebot.adapters import Bot

from idhagnbot.hook.common import (
  CALLED_API_REGISTRY,
  CALLING_API_REGISTRY,
  MESSAGE_SEND_FAILED_HOOKS,
  MESSAGE_SENDING_HOOKS,
  MESSAGE_SENT_HOOKS,
  MessageSendFailedHook,
  MessageSendingHook,
  MessageSentHook,
)

try:
  from idhagnbot.hook.telegram import register
except ImportError:
  pass
else:
  register()

try:
  from idhagnbot.hook.onebot import register
except ImportError:
  pass
else:
  register()

try:
  from idhagnbot.hook.satori import register
except ImportError:
  pass
else:
  register()


T_MessageSendingHook = TypeVar("T_MessageSendingHook", bound=MessageSendingHook)
T_MessageSentHook = TypeVar("T_MessageSentHook", bound=MessageSentHook)
T_MessageSendFailedHook = TypeVar("T_MessageSendFailedHook", bound=MessageSendFailedHook)


@Bot.on_calling_api
async def _(bot: Bot, api: str, data: dict[str, Any]) -> None:
  if MESSAGE_SENDING_HOOKS and (hook := CALLING_API_REGISTRY.get(bot.adapter.get_name())):
    await hook(bot, api, data)


@Bot.on_called_api
async def _(
  bot: Bot,
  e: Optional[Exception],
  api: str,
  data: dict[str, Any],
  result: Any,
) -> None:
  if (MESSAGE_SENT_HOOKS or MESSAGE_SEND_FAILED_HOOKS) and (
    hook := CALLED_API_REGISTRY.get(bot.adapter.get_name())
  ):
    await hook(bot, e, api, data, result)


def on_message_sending(handler: T_MessageSendingHook) -> T_MessageSendingHook:
  MESSAGE_SENDING_HOOKS.append(handler)
  return handler


def on_message_sent(handler: T_MessageSentHook) -> T_MessageSentHook:
  MESSAGE_SENT_HOOKS.append(handler)
  return handler


def on_message_send_failed(handler: T_MessageSendFailedHook) -> T_MessageSendFailedHook:
  MESSAGE_SEND_FAILED_HOOKS.append(handler)
  return handler
