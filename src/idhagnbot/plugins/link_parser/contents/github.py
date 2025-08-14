import re
from typing import Any, Literal, TypedDict

import nonebot
from nonebot_plugin_alconna import Image, UniMessage
from pydantic import TypeAdapter, ValidationError

nonebot.require("nonebot_plugin_alconna")
from idhagnbot.plugins.link_parser.common import FormatState, MatchState

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


def is_same(pathname: str, last_state: dict[str, Any]) -> bool:
  try:
    validated = TypeAdapter(LastState).validate_python(last_state)
    return validated["pathname"] == pathname.lower()
  except ValidationError:
    return False


async def match(link: str, last_state: dict[str, Any]) -> MatchState:
  for regex in REGEXS:
    if match := regex.match(link):
      pathname = match[1]
      if is_same(pathname, last_state):
        return MatchState(False, {})
      return MatchState(True, {"pathname": pathname})
  return MatchState(False, {})


async def format(pathname: str, **kw: Any) -> FormatState:
  return FormatState(
    UniMessage(Image(url=f"https://opengraph.githubassets.com/0/{pathname}")),
    {"type": "github", "pathname": pathname.lower()},
  )
