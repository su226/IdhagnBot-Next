import re
from typing import Any, cast, final

from arclet.entari import MessageChain, Text
from pydantic import TypeAdapter, ValidationError
from typing_extensions import TypedDict

from idhagnbot.asyncio import gather_seq
from idhagnbot.http import get_session
from idhagnbot.plugins.link_parser.common import (
    Content,
    FormatState,
    Matched,
    MatchState,
    Unmatched,
)
from idhagnbot.plugins.link_parser.contents import bilibili_activity, bilibili_video
from idhagnbot.url import clear_url

RE = re.compile(
    r"^(?:[Hh][Tt][Tt][Pp][Ss]?://)?(?:[Bb]23\.[Tt][Vv]|[Bb][Ii][Ll][Ii]2233\.[Cc][Nn])/"
    r"([A-Za-z0-9]{7})(?:\?|#|$)",
)
EXCLUDE_RE = re.compile(r"^av\d{5}$")
CONTENTS: list[Content[Any]] = [bilibili_activity, bilibili_video]


class LastState(TypedDict):
    b23_slug: str


@final
class StateContent(TypedDict):
    slug: str
    content: Content
    state: dict[str, Any]


@final
class StateLink(TypedDict):
    slug: str
    link: str


type State = StateContent | StateLink


def is_same(slug: str, last_state: dict[str, Any]) -> bool:
    try:
        validated = TypeAdapter(LastState).validate_python(last_state)
        return validated["b23_slug"] == slug
    except ValidationError:
        return False


async def match_link(link: str, last_state: dict[str, Any]) -> MatchState[State]:
    match = RE.match(link)
    if not match:
        return Unmatched()
    slug = match[1]
    if EXCLUDE_RE.match(slug) or is_same(slug, last_state):
        return Unmatched()
    async with get_session().get(
        f"https://b23.tv/{slug}",
        allow_redirects=False,
    ) as response:
        location = response.headers.get("Location")
    if not location:
        return Unmatched()
    results = await gather_seq(content.match_link(location, {}) for content in CONTENTS)
    for content, result in zip(CONTENTS, results, strict=True):
        if result.matched:
            return Matched(StateContent(slug=slug, content=content, state=result.state))
    return Matched(StateLink(slug=slug, link=location))


async def format_link(state: State) -> FormatState:
    slug = state["slug"]
    if "link" in state:
        link = cast("str", state["link"])
        link_cleared = clear_url(link)
        text = (
            "短链解析结果（已清除跟踪参数）: "
            if link_cleared != link
            else "短链解析结果: "
        )
        return FormatState(MessageChain(Text(text + link_cleared)), {"b23_slug": slug})
    result = await state["content"].format_link(state["state"])
    result.state.update({"b23_slug": slug})
    return result
