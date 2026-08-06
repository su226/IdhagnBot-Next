import re
from typing import Any, Literal

from arclet.entari import Image, MessageChain
from pydantic import TypeAdapter, ValidationError
from typing_extensions import TypedDict

from idhagnbot.plugins.link_parser.common import (
    FormatState,
    Matched,
    MatchState,
    Unmatched,
)

REGEXS = [
    re.compile(
        r"^(?:https?://)?(?:www\.)?github\.com/([a-z0-9-]+/[a-z0-9\._-]+)/?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:https?://)?(?:www\.)?github\.com/([a-z0-9-]+/[a-z0-9\._-]+/issues/\d+)/?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:https?://)?(?:www\.)?github\.com/([a-z0-9-]+/[a-z0-9\._-]+/pull/\d+)/?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:https?://)?(?:www\.)?github\.com/([a-z0-9-]+/[a-z0-9\._-]+/commit/[0-9a-f]{40})/?$",
        re.IGNORECASE,
    ),
]


class LastState(TypedDict):
    type: Literal["github"]
    pathname: str


class State(TypedDict):
    pathname: str


def is_same(pathname: str, last_state: dict[str, Any]) -> bool:
    try:
        validated = TypeAdapter(LastState).validate_python(last_state)
        return validated["pathname"] == pathname.lower()
    except ValidationError:
        return False


async def match_link(link: str, last_state: dict[str, Any]) -> MatchState[State]:
    for regex in REGEXS:
        if match := regex.match(link):
            pathname = match[1]
            if is_same(pathname, last_state):
                return Unmatched()
            return Matched(State(pathname=pathname))
    return Unmatched()


async def format_link(state: State) -> FormatState:
    pathname = state["pathname"]
    return FormatState(
        MessageChain(Image(f"https://opengraph.githubassets.com/0/{pathname}")),
        {"type": "github", "pathname": pathname.lower()},
    )
