from enum import Enum

import nonebot
from pydantic import BaseModel

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Target


class TargetType(Enum):
  PRIVATE = "private"
  GROUP = "group"
  CHANNEL = "channel"


class TargetConfig(BaseModel, extra="allow"):
  type: TargetType
  id: str
  parent_id: str = ""
  self_id: str = ""
  scope: str = ""
  adapter: str = ""
  platform: str = ""

  @property
  def target(self) -> Target:
    return Target(
      self.id,
      self.parent_id,
      channel=self.type == TargetType.CHANNEL,
      private=self.type == TargetType.PRIVATE,
      self_id=self.self_id,
      scope=self.scope,
      adapter=self.adapter,
      platform=self.platform,
      extra=self.model_extra,
    )
