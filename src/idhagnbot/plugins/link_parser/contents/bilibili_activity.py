import re
from typing import Any, Literal

from pydantic import TypeAdapter, ValidationError
from typing_extensions import TypedDict

from idhagnbot.plugins.bilibili_activity.contents import format_activity
from idhagnbot.plugins.link_parser.common import (
    FormatState,
    Matched,
    MatchState,
    Unmatched,
)
from idhagnbot.third_party.bilibili_activity import Activity, get

RE = re.compile(
    r"^(?:[Hh][Tt][Tt][Pp][Ss]?://)?(?:[Tt]\.[Bb][Ii][Ll][Ii][Bb][Ii][Ll][Ii]\.[Cc][Oo][Mm]|"
    r"(?:[Ww][Ww][Ww]\.|[Mm]\.)?[Bb][Ii][Ll][Ii][Bb][Ii][Ll][Ii]\.[Cc][Oo][Mm]/opus)/(\d+)/?(?:\?|#|$)",
)


class LastState(TypedDict):
    type: Literal["bilibili_activity"]
    activity_id: int


class State(TypedDict):
    activity_id: int


def is_same(activity_id: int, last_state: dict[str, Any]) -> bool:
    try:
        validated = TypeAdapter(LastState).validate_python(last_state)
        return validated["activity_id"] == activity_id
    except ValidationError:
        return False


async def match_link(link: str, last_state: dict[str, Any]) -> MatchState[State]:
    if match := RE.match(link):
        activity_id = int(match[1])
        if not is_same(activity_id, last_state):
            return Matched(State(activity_id=activity_id))
    return Unmatched()


async def format_link(state: State) -> FormatState:
    activity = Activity.parse(await get(state["activity_id"]))
    message = await format_activity(activity, can_ignore=False)
    return FormatState(
        message,
        {"type": "bilibili_activity", "activity_id": state["activity_id"]},
    )
