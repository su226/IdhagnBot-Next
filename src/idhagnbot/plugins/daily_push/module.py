from typing import Callable, Protocol, TypeVar, Union

import nonebot
from pydantic import BaseModel

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Target
from nonebot_plugin_alconna.uniseg import Segment, UniMessage


class Module(Protocol):
  async def format(self) -> list[UniMessage[Segment]]: ...


class ModuleConfig(BaseModel):
  def create_module(self) -> Module:
    raise NotImplementedError


class TargetAwareModuleConfig(BaseModel):
  def create_module(self, target: Target) -> Module:
    raise NotImplementedError


MODULE_REGISTRY: dict[str, type[Union[ModuleConfig, TargetAwareModuleConfig]]] = {}
T = TypeVar("T", bound=Union[ModuleConfig, TargetAwareModuleConfig])


def register(name: str) -> Callable[[type[T]], type[T]]:
  def decorator(config_type: type[T]) -> type[T]:
    MODULE_REGISTRY[name] = config_type
    return config_type

  return decorator
