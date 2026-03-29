import nonebot
from nonebot.plugin import PluginMetadata

from idhagnbot.permission import permission

__plugin_meta__ = PluginMetadata(
  name="戳回去",
  description="在机器人收到戳一戳时戳一戳用户，表明机器人还活着。",
  usage="戳一戳机器人",
  type="application",
  homepage="https://github.com/su226/IdhagnBot-Next",
  supported_adapters={"~onebot.v11"},
)

try:
  from nonebot.adapters.onebot.v11 import Bot, PokeNotifyEvent
except ImportError:
  pass
else:
  from idhagnbot.onebot import send_poke

  async def check_poke_back(event: PokeNotifyEvent) -> bool:
    return event.user_id != event.self_id and event.target_id == event.self_id

  poke_back = nonebot.on_notice(check_poke_back, permission("poke_back"))

  @poke_back.handle()
  async def handle_poke_back(bot: Bot, event: PokeNotifyEvent) -> None:
    await send_poke(bot, event)
