import re
from typing import Any, Literal, TypedDict

import nonebot
from pydantic import TypeAdapter, ValidationError

from idhagnbot.plugins.link_parser.common import FormatState, MatchState
from idhagnbot.third_party.bilibili_activity import Activity, get

nonebot.require("idhagnbot.plugins.bilibili_activity")
from idhagnbot.plugins.bilibili_activity.contents import format as format_activity

RE = re.compile(
  r"^(?:[Hh][Tt][Tt][Pp][Ss]?://)?(?:[Tt]\.[Bb][Ii][Ll][Ii][Bb][Ii][Ll][Ii]\.[Cc][Oo][Mm]|"
  r"(?:[Ww][Ww][Ww]\.|[Mm]\.)?[Bb][Ii][Ll][Ii][Bb][Ii][Ll][Ii]\.[Cc][Oo][Mm]/opus)/(\d+)/?(?:\?|#|$)",
)


class LastState(TypedDict):
  type: Literal["bilibili_activity"]
  id: int


def is_same(id: int, last_state: dict[str, Any]) -> bool:
  try:
    validated = TypeAdapter(LastState).validate_python(last_state)
    return validated["id"] == id
  except ValidationError:
    return False


async def match(link: str, last_state: dict[str, Any]) -> MatchState:
  if match := RE.match(link):
    id = int(match[1])
    if not is_same(id, last_state):
      return MatchState(True, {"id": id})
  return MatchState(False, {})


async def format(id: int, **kw: Any) -> FormatState:
  activity = Activity.parse(await get(id))
  message = await format_activity(activity, False)
  return FormatState(message, {"type": "bilibili_activity", "id": id})
