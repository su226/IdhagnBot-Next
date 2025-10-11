import nonebot
from nonebot.adapters import Bot, Event
from nonebot.consts import CMD_KEY, PREFIX_KEY
from nonebot.typing import T_State
from pydantic import BaseModel

from idhagnbot.config import SharedConfig
from idhagnbot.message.common import OrigUniMsg
from idhagnbot.permission import permission
from idhagnbot.plugins.interaction.common import REPLY_EXTRACT_REGISTRY

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Reply, Text, command_manager
from nonebot_plugin_uninfo import Uninfo

try:
  from idhagnbot.plugins.interaction.onebot import register
except ImportError:
  pass
else:
  register()
try:
  from idhagnbot.plugins.interaction.telegram import register
except ImportError:
  pass
else:
  register()


class Config(BaseModel):
  active_prefix: str = "/"
  passive_prefix: str = "\\"
  max_length: int = 10


CONFIG = SharedConfig("interaction", Config)


async def check_interaction(bot: Bot, event: Event, message: OrigUniMsg, state: T_State) -> bool:
  if state[PREFIX_KEY][CMD_KEY]:
    return False
  extractor = REPLY_EXTRACT_REGISTRY.get(bot.adapter.get_name())
  if not extractor:
    return False
  reply_segments = message[Reply]
  if len(reply_segments) != 1:
    return False
  text_segments = message[Text]
  if len(text_segments) + 1 < len(message):
    return False
  text = text_segments.extract_plain_text()
  if command_manager.test(text):
    return False
  config = CONFIG()
  if text.startswith(config.active_prefix):
    action = text[1:]
    passive = False
  elif text.startswith(config.passive_prefix):
    action = text[1:]
    passive = True
  else:
    return False
  if len(action) > config.max_length:
    return False
  state["action"] = action
  state["passive"] = passive
  state["user2"] = await extractor(bot, event, reply_segments[0])
  return True


interaction = nonebot.on_message(check_interaction, permission("interaction"))


@interaction.handle()
async def _(state: T_State, session: Uninfo) -> None:
  user1 = session.user.nick or session.user.name or session.user.id
  if state["passive"]:
    await interaction.finish(f"{user1} 被 {state['user2']} {state['action']}了")
  else:
    await interaction.finish(f"{user1} {state['action']}了 {state['user2']}")
