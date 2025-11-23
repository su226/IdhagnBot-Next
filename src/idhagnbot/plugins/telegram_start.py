import nonebot

from idhagnbot.help import COMMAND_PREFIX
from idhagnbot.message import UniMsg

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Text
from nonebot_plugin_uninfo import SupportScope, Uninfo


async def check_start(session: Uninfo, message: UniMsg) -> bool:
  return (
    session.scope == SupportScope.telegram
    and len(message) == 1
    and isinstance(segment := message[0], Text)
    and segment.text == "/start"
  )


start = nonebot.on_message(check_start)


@start.handle()
async def _() -> None:
  await start.finish(f"欢迎使用 IdhagnBot Next，请发送 {COMMAND_PREFIX}help 以获取帮助。")
