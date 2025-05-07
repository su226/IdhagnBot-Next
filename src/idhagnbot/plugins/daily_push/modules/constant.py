from typing import Any, Union

import nonebot

from idhagnbot.plugins.daily_push.module import Module, ModuleConfig

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, Text, UniMessage


class ConstantModuleConfig(ModuleConfig):
  message: Union[str, list[dict[str, Any]]]

  def create_module(self) -> Module:
    if isinstance(self.message, str):
      message = UniMessage[Segment](Text(self.message))
    else:
      message = UniMessage.load(self.message)
    return ConstantModule(message)


class ConstantModule(Module):
  def __init__(self, message: UniMessage[Segment]) -> None:
    self.message = message

  async def format(self) -> list[UniMessage[Segment]]:
    return [self.message]
