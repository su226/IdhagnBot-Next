from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from arclet.entari import MessageChain
from pydantic import BaseModel


@dataclass(frozen=True)
class Target:
    platform: str
    guild_id: str | None
    channel_id: str


class SimpleModule(BaseModel):
    type: ClassVar[str]

    async def format(self) -> list[MessageChain]:
        raise NotImplementedError


class TargetAwareModule(BaseModel):
    type: ClassVar[str]

    async def format(self, target: Target) -> list[MessageChain]:
        raise NotImplementedError


class ComplexModule(BaseModel):
    type: ClassVar[str]

    async def format(self, targets: list[Target]) -> dict[Target, list[MessageChain]]:
        raise NotImplementedError


type Module = SimpleModule | TargetAwareModule | ComplexModule
MODULE_REGISTRY: dict[str, type[Module]] = {}


def register[T: Module](config_type: type[T]) -> Callable[[], None]:
    if config_type.type in MODULE_REGISTRY:
        raise ValueError(f"已有类型为 {config_type.type} 的模块")
    MODULE_REGISTRY[config_type.type] = config_type

    def dispose() -> None:
        MODULE_REGISTRY.pop(config_type.type, None)

    return dispose


class ModuleConfig(BaseModel, extra="allow"):
    type: str

    def to_module(self) -> Module:
        return MODULE_REGISTRY[self.type].model_validate(self.model_extra)
