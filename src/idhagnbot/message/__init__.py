from idhagnbot.message.common import MergedEvent, MergedMsg, UniMsg

__all__ = ["MergedEvent", "MergedMsg", "UniMsg"]

try:
  from idhagnbot.message.telegram import register
except ImportError:
  pass
else:
  register()
