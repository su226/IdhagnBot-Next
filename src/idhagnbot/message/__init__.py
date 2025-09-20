from idhagnbot.message.common import (
  EventTime,
  MergedEvent,
  MergedMsg,
  MessageId,
  UniMsg,
  send_message,
)

__all__ = ["EventTime", "MergedEvent", "MergedMsg", "MessageId", "UniMsg", "send_message"]

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
