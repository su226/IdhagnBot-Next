from dataclasses import dataclass
from typing import Any, Protocol

import nonebot

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Segment, UniMessage


@dataclass
class MatchState:
  matched: bool
  state: dict[str, Any]


@dataclass
class FormatState:
  message: UniMessage[Segment]
  state: dict[str, Any]


class Content(Protocol):
  @staticmethod
  async def match_link(link: str, last_state: dict[str, Any]) -> MatchState: ...
  @staticmethod
  async def format_link(**kw: Any) -> FormatState: ...
