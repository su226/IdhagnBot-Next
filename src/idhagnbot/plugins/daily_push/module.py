from collections.abc import Callable
from typing import TypeVar

import nonebot
from pydantic import BaseModel

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Target
from nonebot_plugin_alconna.uniseg import Segment, UniMessage


class SimpleModule(BaseModel):
  async def format(self) -> list[UniMessage[Segment]]:
    raise NotImplementedError


class TargetAwareModule(BaseModel):
  async def format(self, target: Target) -> list[UniMessage[Segment]]:
    raise NotImplementedError


MODULE_REGISTRY: dict[str, type[SimpleModule | TargetAwareModule]] = {}
T = TypeVar("T", bound=SimpleModule | TargetAwareModule)


def register(name: str) -> Callable[[type[T]], type[T]]:
  def decorator(config_type: type[T]) -> type[T]:
    if name in MODULE_REGISTRY:
      raise ValueError(f"已有类型为 {name} 的模块")
    MODULE_REGISTRY[name] = config_type
    return config_type

  return decorator
