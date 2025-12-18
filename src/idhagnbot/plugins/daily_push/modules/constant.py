from typing import Any

import nonebot
from typing_extensions import override

from idhagnbot.plugins.daily_push.module import SimpleModule

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, Text, UniMessage


class ConstantModule(SimpleModule):
  message: str | list[dict[str, Any]]

  @override
  async def format(self) -> list[UniMessage[Segment]]:
    if isinstance(self.message, str):
      message = UniMessage[Segment](Text(self.message))
    else:
      message = UniMessage.load(self.message)
    return [message]
