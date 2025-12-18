import re
from typing import Any, Literal

import nonebot
from pydantic import TypeAdapter, ValidationError
from typing_extensions import TypedDict

from idhagnbot.plugins.link_parser.common import FormatState, MatchState
from idhagnbot.third_party.bilibili_activity import Activity, get

nonebot.require("idhagnbot.plugins.bilibili_activity")
from idhagnbot.plugins.bilibili_activity.contents import format_activity

RE = re.compile(
  r"^(?:[Hh][Tt][Tt][Pp][Ss]?://)?(?:[Tt]\.[Bb][Ii][Ll][Ii][Bb][Ii][Ll][Ii]\.[Cc][Oo][Mm]|"
  r"(?:[Ww][Ww][Ww]\.|[Mm]\.)?[Bb][Ii][Ll][Ii][Bb][Ii][Ll][Ii]\.[Cc][Oo][Mm]/opus)/(\d+)/?(?:\?|#|$)",
)


class LastState(TypedDict):
  type: Literal["bilibili_activity"]
  activity_id: int


def is_same(activity_id: int, last_state: dict[str, Any]) -> bool:
  try:
    validated = TypeAdapter(LastState).validate_python(last_state)
    return validated["activity_id"] == activity_id
  except ValidationError:
    return False


async def match_link(link: str, last_state: dict[str, Any]) -> MatchState:
  if match := RE.match(link):
    activity_id = int(match[1])
    if not is_same(activity_id, last_state):
      return MatchState(matched=True, state={"activity_id": activity_id})
  return MatchState(matched=False, state={})


async def format_link(activity_id: int, **kw: Any) -> FormatState:
  activity = Activity.parse(await get(activity_id))
  message = await format_activity(activity, can_ignore=False)
  return FormatState(message, {"type": "bilibili_activity", "activity_id": activity_id})
