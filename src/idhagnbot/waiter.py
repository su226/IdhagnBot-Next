import nonebot

from idhagnbot.message import UniMsg

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_waiter")
from nonebot_plugin_alconna import Segment, UniMessage
from nonebot_plugin_waiter import waiter  # pyright: ignore[reportMissingTypeStubs]


async def prompt() -> UniMessage[Segment] | None:
  @waiter(["message"], keep_session=True)
  async def prompter(message: UniMsg) -> UniMsg:
    return message

  return await prompter.wait()
