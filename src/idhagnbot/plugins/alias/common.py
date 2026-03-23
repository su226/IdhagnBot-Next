from collections.abc import Callable
from dataclasses import dataclass

from nonebot.adapters import Event
from pydantic import BaseModel, Field

from idhagnbot.config import SharedConfig


@dataclass
class Alias:
  name: str
  definition: str


class Config(BaseModel):
  aliases: dict[str, dict[str, str | None]] = Field(default_factory=dict)

  def get_replacement(self, scene_id: str, name: str) -> Alias | None:
    aliases = self.aliases.get(scene_id)
    if not aliases:
      return None
    # nonebot_plugin_alconna 和 nonebot 不同，要求命令后面一定要有空格，因此不需要字典树匹配
    pos = 0
    for char in name:
      if char.isspace():
        break
      pos += 1
    name = name[:pos]
    definition = aliases.get(name)
    return Alias(name, definition) if definition else None


CONFIG = SharedConfig("alias", Config)
COMMAND_UPDATER_REGISTRY = dict[str, Callable[[str, Event], None]]()
