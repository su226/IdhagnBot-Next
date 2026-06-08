from typing import cast

import nonebot

from idhagnbot.message import UniMsg

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_waiter")
from nonebot_plugin_alconna import Segment, UniMessage
from nonebot_plugin_waiter import waiter


async def prompt() -> UniMessage[Segment] | None:
  @waiter(["message"], keep_session=True)
  async def prompter(message: UniMsg) -> UniMessage[Segment]:
    return message

  return cast("UniMessage[Segment] | None", await prompter.wait())
