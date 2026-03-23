import nonebot
from nonebot.adapters import Bot, Event
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor, run_preprocessor
from nonebot.typing import T_State

from idhagnbot.context import SceneIdOnePrivate
from idhagnbot.message import OrigUniMsg
from idhagnbot.plugins.alias.common import COMMAND_UPDATER_REGISTRY, CONFIG

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import ALCONNA_RESULT, CommandResult, Segment, Text, UniMessage

try:
  from idhagnbot.plugins.alias.onebot import register
except ImportError:
  pass
else:
  register()
try:
  from idhagnbot.plugins.alias.satori import register
except ImportError:
  pass
else:
  register()
try:
  from idhagnbot.plugins.alias.telegram import register
except ImportError:
  pass
else:
  register()


@event_preprocessor
async def _(bot: Bot, scene_id: SceneIdOnePrivate, event: Event) -> None:
  if event.get_type() != "message":
    return
  command_updater = COMMAND_UPDATER_REGISTRY.get(bot.adapter.get_name())
  if command_updater:
    command_updater(scene_id, event)


def command_match(unimsg: UniMessage[Segment], command: str) -> bool:
  if isinstance(segment := unimsg[0], Text):
    return segment.text.lstrip().startswith(command)
  return False


@run_preprocessor
async def _(scene_id: SceneIdOnePrivate, state: T_State, orig_unimsg: OrigUniMsg) -> None:
  result: CommandResult | None = state.get(ALCONNA_RESULT)
  if not result:
    return
  header: str = result.result.header_match.origin
  config = CONFIG()
  aliases = config.aliases.get(scene_id)
  if not aliases or header not in aliases:
    return
  alias = aliases[header]
  if alias is None and command_match(orig_unimsg, header):
    raise IgnoredException("忽略该别名")
