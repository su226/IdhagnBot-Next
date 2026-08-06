from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from arclet.entari import MessageChain


@dataclass
class Unmatched:
    matched: Literal[False] = field(default=False, init=False)


@dataclass
class Matched[T: Mapping[str, Any]]:
    matched: Literal[True] = field(default=True, init=False)
    state: T


type MatchState[T: Mapping[str, Any]] = Unmatched | Matched[T]


@dataclass
class FormatState[T: Mapping[str, Any]]:
    message: MessageChain
    state: T


class Content[T: Mapping[str, Any]](Protocol):
    @staticmethod
    async def match_link(link: str, last_state: dict[str, Any]) -> MatchState[T]: ...
    @staticmethod
    async def format_link(state: T) -> FormatState[T]: ...
