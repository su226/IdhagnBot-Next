import asyncio
import re
from typing import Any, Optional, TypedDict

import nonebot
from pydantic import TypeAdapter, ValidationError

from idhagnbot.http import get_session
from idhagnbot.plugins.link_parser.common import Content, FormatState, MatchState
from idhagnbot.plugins.link_parser.contents import bilibili_activity, bilibili_video

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Text, UniMessage

RE = re.compile(
  r"^(?:[Hh][Tt][Tt][Pp][Ss]?://)?(?:[Bb]23\.[Tt][Vv]|[Bb][Ii][Ll][Ii]2233\.[Cc][Nn])/"
  r"([A-Za-z0-9]{7})(?:\?|#|$)",
)
EXCLUDE_RE = re.compile(r"^av\d{5}$")
CONTENTS: list[Content] = [bilibili_activity, bilibili_video]


class LastState(TypedDict):
  b23_slug: str


def is_same(slug: str, last_state: dict[str, Any]) -> bool:
  try:
    validated = TypeAdapter(LastState).validate_python(last_state)
    return validated["b23_slug"] == slug
  except ValidationError:
    return False


async def match(link: str, last_state: dict[str, Any]) -> MatchState:
  match = RE.match(link)
  if not match:
    return MatchState(False, {})
  slug = match[1]
  if EXCLUDE_RE.match(slug) or is_same(slug, last_state):
    return MatchState(False, {})
  async with get_session().get(f"https://b23.tv/{slug}", allow_redirects=False) as response:
    location = response.headers.get("Location")
  if not location:
    return MatchState(False, {})
  results = await asyncio.gather(*[content.match(location, {}) for content in CONTENTS])
  for content, result in zip(CONTENTS, results):
    if result.matched:
      return MatchState(
        True,
        {
          "slug": slug,
          "link": location,
          "content": content,
          "state": result.state,
        },
      )
  return MatchState(
    True,
    {
      "slug": slug,
      "link": location,
      "content": None,
      "state": {},
    },
  )


async def format(
  slug: str,
  link: str,
  content: Optional[Content],
  state: dict[str, Any],
  **kw: Any,
) -> FormatState:
  if content is None:
    return FormatState(UniMessage(Text("短链解析结果: " + link)), {"b23_slug": slug})
  result = await content.format(**state)
  result.state.update({"b23_slug": slug})
  return result
