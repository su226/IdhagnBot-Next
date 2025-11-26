import re
import time
from io import BytesIO
from typing import Any, Literal

import nonebot
from anyio.to_thread import run_sync
from PIL import Image
from pydantic import TypeAdapter, ValidationError
from typing_extensions import TypedDict

from idhagnbot.http import BROWSER_UA, get_session
from idhagnbot.image import to_segment
from idhagnbot.image.card import (
  Card,
  CardAuthor,
  CardCover,
  CardInfo,
  CardText,
  InfoCount,
  InfoText,
)
from idhagnbot.plugins.link_parser.common import FormatState, MatchState
from idhagnbot.third_party.bilibili_auth import validate_result

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Image as ImageSeg
from nonebot_plugin_alconna.uniseg import Text, UniMessage

RE1 = re.compile(
  r"^(?:[Hh][Tt][Tt][Pp][Ss]?://)?(?:[Bb]23\.[Tt][Vv]|[Bb][Ii][Ll][Ii]2233\.[Cc][Nn])/"
  r"(av\d{1,15}|BV[A-Za-z0-9]{10})(?:\?|#|$)",
)
RE2 = re.compile(
  r"^(?:[Hh][Tt][Tt][Pp][Ss]?://)?(?:[Ww][Ww][Ww]\.|[Mm]\.)?[Bb][Ii][Ll][Ii][Bb][Ii][Ll][Ii]\."
  r"[Cc][Oo][Mm]/video/(av\d{1,15}|(?:BV|bv)[A-Za-z0-9]{10})/?(?:\?|#|$)",
)
INFO_API = "https://api.bilibili.com/x/web-interface/view/detail"


def match_link(link: str) -> str | None:
  if match := RE1.match(link):
    return match[1]
  if match := RE2.match(link):
    return match[1]
  return None


class LastState(TypedDict):
  type: Literal["bilibili_video"]
  aid: int
  bvid: str


def is_aid_same(aid: int, last_state: dict[str, Any]) -> bool:
  try:
    validated = TypeAdapter(LastState).validate_python(last_state)
    return validated["aid"] == aid
  except ValidationError:
    return False


def is_bvid_same(bvid: str, last_state: dict[str, Any]) -> bool:
  try:
    validated = TypeAdapter(LastState).validate_python(last_state)
    return validated["bvid"] == bvid
  except ValidationError:
    return False


class ApiStat(TypedDict):
  view: int
  danmaku: int
  reply: int
  like: int
  coin: int
  favorite: int
  share: int


class ApiView(TypedDict):
  bvid: str
  aid: int
  videos: int
  copyright: int
  pic: str
  title: str
  pubdate: int
  desc: str
  duration: int
  stat: ApiStat


class ApiCardInner(TypedDict):
  name: str
  face: str
  fans: int


class ApiCard(TypedDict):
  card: ApiCardInner


class ApiTag(TypedDict):
  tag_name: str
  tag_type: str


class ApiResult(TypedDict):
  View: ApiView
  Card: ApiCard
  Tags: list[ApiTag]


def format_duration(seconds: int) -> str:
  minutes, seconds = divmod(seconds, 60)
  hours, minutes = divmod(minutes, 24)
  if hours:
    return f"{hours:02}:{minutes:02}:{seconds:02}"
  return f"{minutes:02}:{seconds:02}"


async def match(link: str, last_state: dict[str, Any]) -> MatchState:
  video = match_link(link)
  if not video:
    return MatchState(False, {})
  if video[:2] == "av":
    aid = video[2:]
    if is_aid_same(int(aid), last_state):
      return MatchState(False, {})
    params = {"aid": aid}
  else:
    if is_bvid_same(video, last_state):
      return MatchState(False, {})
    params = {"bvid": video}
  async with get_session().get(
    INFO_API,
    headers={"User-Agent": BROWSER_UA},
    params=params,
  ) as response:
    data = await response.json()
  if data["code"] in (-404, 62002, 62004, 62012):  # 不存在、不可见、审核中、仅UP主自己可见
    return MatchState(False, {})
  result = validate_result(data, ApiResult)
  return MatchState(True, {"data": result})


async def format(
  data: ApiResult,
  **kw: Any,
) -> FormatState:
  # 1. 获取视频信息、封面、UP主头像
  data_view = data["View"]
  data_card = data["Card"]["card"]
  data_stat = data_view["stat"]

  http = get_session()
  async with http.get(data_card["face"]) as response:
    avatar_data = await response.read()
  async with http.get(data_view["pic"]) as response:
    cover_data = await response.read()

  def make() -> ImageSeg:
    # 2. 构建卡片
    card = Card(0)

    block = Card()
    block.add(CardText(data_view["title"], size=40, lines=2))
    avatar = Image.open(BytesIO(avatar_data))
    block.add(CardAuthor(avatar, data_card["name"], data_card["fans"]))
    card.add(block)

    cover = Image.open(BytesIO(cover_data))
    card.add(CardCover(cover))

    block = Card()
    infos = CardInfo()
    date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data_view["pubdate"]))
    infos.add(InfoText(date))
    infos.add(InfoText("转载" if data_view["copyright"] == 2 else "自制"))
    duration = format_duration(data_view["duration"])
    if (parts := data_view["videos"]) > 1:
      duration = f"{parts}P共{duration}"
    infos.add(InfoText(duration))
    infos.add(InfoCount("play", data_stat["view"]))
    infos.add(InfoCount("danmaku", data_stat["danmaku"]))
    infos.add(InfoCount("comment", data_stat["reply"]))
    infos.add(InfoCount("like", data_stat["like"]))
    infos.add(InfoCount("coin", data_stat["coin"]))
    infos.add(InfoCount("collect", data_stat["favorite"]))
    infos.add(InfoCount("share", data_stat["share"]))
    block.add(infos)
    desc = data_view["desc"]
    if desc and desc != "-":
      block.add(CardText(desc, size=28, lines=3, color=(102, 102, 102)))
    if tags := data["Tags"]:
      infos = CardInfo(8)
      for tag in tags:
        if tag["tag_type"] != "bgm":
          infos.add(InfoText("#" + tag["tag_name"], 26))
      block.add(infos)
    card.add(block)

    # 3. 渲染卡片并发送
    im = Image.new("RGB", (card.get_width(), card.get_height()), (255, 255, 255))
    card.render(im, 0, 0)
    return to_segment(im)

  bvid = data_view["bvid"]
  aid = data_view["aid"]
  return FormatState(
    UniMessage([await run_sync(make), Text(f"https://b23.tv/{bvid} (av{aid})")]),
    {"type": "bilibili_video", "aid": aid, "bvid": bvid},
  )
