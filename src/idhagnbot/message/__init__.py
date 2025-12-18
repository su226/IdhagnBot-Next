import nonebot
from nonebot.matcher import current_bot, current_event

from idhagnbot.message.common import (
  EventTime,
  MaybeReplyInfo,
  MergedEvent,
  MergedMsg,
  MessageId,
  OrigMergedMsg,
  OrigUniMsg,
  ReplyInfo,
  UniMsg,
  send_message,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Image, UniMessage

try:
  from nonebot.adapters.telegram import Bot as TGBot
  from nonebot.adapters.telegram import Event as TGEvent
  from nonebot.adapters.telegram import Message as TGMessage
  from nonebot.adapters.telegram.message import File as TGFile
except ImportError:
  TGBot = None
  TGEvent = None
  TGMessage = None
  TGFile = None

__all__ = [
  "EventTime",
  "MaybeReplyInfo",
  "MergedEvent",
  "MergedMsg",
  "MessageId",
  "OrigMergedMsg",
  "OrigUniMsg",
  "ReplyInfo",
  "UniMsg",
  "send_image_or_animation",
  "send_message",
]

try:
  from idhagnbot.message.onebot import register
except ImportError:
  pass
else:
  register()
try:
  from idhagnbot.message.satori import register
except ImportError:
  pass
else:
  register()
try:
  from idhagnbot.message.telegram import register
except ImportError:
  pass
else:
  register()


async def send_image_or_animation(image: Image) -> str:
  uni = UniMessage(image)
  bot = current_bot.get()
  if bot.adapter.get_name() == "Telegram" and (
    image.name.endswith(".gif") or image.mimetype == "image/gif"
  ):  # TODO: 为这个设计合适的注册表机制
    assert TGBot
    assert isinstance(bot, TGBot)
    message = await uni.export(bot)
    assert TGMessage
    assert isinstance(message, TGMessage)
    segment = message[0]
    assert TGFile
    assert isinstance(segment, TGFile)
    segment.type = "animation"
    event = current_event.get()
    assert TGEvent
    assert isinstance(event, TGEvent)
    receipt = await bot.send(event, message)
    return receipt.message_id
  receipt = await send_message(uni)
  return receipt[0]
