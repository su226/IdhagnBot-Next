from dataclasses import dataclass
from datetime import datetime
from itertools import count
from typing import Protocol
from urllib.parse import quote as encodeuri

import nonebot
from anyio.to_thread import run_sync
from nonebot.exception import FinishedException
from nonebot.typing import T_State
from PIL import Image, ImageDraw, ImageOps
from typing_extensions import NotRequired, TypedDict

from idhagnbot.color import split_rgb
from idhagnbot.command import CommandBuilder
from idhagnbot.http import BROWSER_UA, get_session
from idhagnbot.image import circle, get_resample, get_scale_resample, open_url, to_segment
from idhagnbot.plugins.bilibili_check import vtb
from idhagnbot.plugins.bilibili_check.common import CACHE, CONFIG, CacheItem
from idhagnbot.text import Layout, layout, render
from idhagnbot.third_party.bilibili_auth import (
  ApiError,
  get_cookie,
  validate_biligame_result,
  validate_result,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, UniMessage
from nonebot_plugin_alconna import Image as ImageSeg

SEARCH_API = "http://api.bilibili.com/x/web-interface/search/type?search_type=bili_user&keyword={}"
INFO_API = "http://api.bilibili.com/x/web-interface/card?mid={}"
FOLLOW_API = "https://line3-h5-mobile-api.biligame.com/game/center/h5/user/relationship/following_list?vmid={vmid}&ps=50&pn={pn}"
MEDAL_API = "https://api.live.bilibili.com/xlive/web-ucenter/user/MedalWall?target_id={}"
GRADIENT_45DEG_WH = 362.038671968  # 256 * sqrt(2)


class SearchItem(TypedDict):
  mid: int


class SearchResult(TypedDict):
  result: NotRequired[list[SearchItem]]


class InfoCard(TypedDict):
  name: str
  fans: int
  attention: int
  face: str


class InfoResult(TypedDict):
  card: InfoCard


class FollowingItem(TypedDict):
  mid: str
  uname: str


class FollowingResult(TypedDict):
  list: list[FollowingItem]


class MedalInfo(TypedDict):
  target_id: int
  level: int
  medal_name: str
  medal_color_start: int
  medal_color_end: int
  medal_color_border: int


class MedalItem(TypedDict):
  medal_info: MedalInfo


class MedalResult(TypedDict):
  list: list[MedalItem]


class Provider(Protocol):
  @staticmethod
  def get_id() -> str: ...
  @staticmethod
  def get_name() -> str: ...
  @staticmethod
  def get_command() -> str: ...
  @staticmethod
  def get_description() -> str: ...
  @staticmethod
  async def get_uids() -> set[int]: ...


def register(provider: Provider) -> None:
  command = (
    CommandBuilder()
    .node(f"bilibili_check.{provider.get_id()}")
    .parser(
      Alconna(
        provider.get_command(),
        Args["id_or_name#B 站 UID 或用户名", str],
        meta=CommandMeta(provider.get_description()),
      ),
    )
    .state({"provider": provider})
    .build()
  )
  command.handle()(handle_bilibili_check)


@dataclass
class User:
  id: int
  name: str


@dataclass
class LayoutedMedal:
  name_layout: Layout
  level_layout: Layout
  width: int
  color_border: int
  color_start: int
  color_end: int


def make_list_item(name: str, uid: int, medal: MedalInfo | None) -> Image.Image:
  name_im = render(name, "sans", 32)
  uid_im = render(str(uid), "sans", 28)

  padding = 6
  border = 2
  margin = 12
  uid_width = uid_im.width + padding * 2
  im_width = name_im.width + margin + uid_width
  layouted_medal = None
  if medal:
    medal_name_layout = layout(medal["medal_name"], "sans", 28)
    medal_level_layout = layout(str(medal["level"]), "sans", 28)
    medal_width = (
      medal_name_layout.get_pixel_size()[0]
      + medal_level_layout.get_pixel_size()[0]
      + padding * 4
      + border * 2
    )
    im_width += margin + medal_width
    layouted_medal = LayoutedMedal(
      medal_name_layout,
      medal_level_layout,
      medal_width,
      medal["medal_color_border"],
      medal["medal_color_start"],
      medal["medal_color_end"],
    )
  im = Image.new("RGBA", (im_width, name_im.height))

  im.paste(name_im, (0, 0), name_im)
  x = name_im.width + margin

  y = (im.height - uid_im.height) // 2
  rounded_im = Image.new("L", (uid_width * 2, uid_im.height * 2), 0)
  ImageDraw.Draw(rounded_im).rounded_rectangle(
    (0, 0, uid_width * 2 - 1, uid_im.height * 2 - 1),
    8,
    255,
  )
  rounded_im = rounded_im.resize((uid_width, uid_im.height), get_scale_resample())
  im.paste((221, 221, 221), (x, y), rounded_im)
  im.paste(uid_im, (x + padding, y), uid_im)
  x += uid_width + margin
  if not layouted_medal:
    return im

  medal_name_im = render(layouted_medal.name_layout, color=(255, 255, 255))
  border_color = split_rgb(layouted_medal.color_border)
  medal_level_im = render(layouted_medal.level_layout, color=border_color)

  medal_height = medal_name_im.height + border * 2
  y = (im.height - medal_height) // 2
  im.paste(border_color, (x, y, x + layouted_medal.width, y + medal_height))

  medal_name_bg_width = medal_name_im.width + padding * 2
  ratio = medal_name_bg_width / medal_name_im.height
  gradient = ImageOps.colorize(
    Image.linear_gradient("L"),
    split_rgb(layouted_medal.color_start),
    split_rgb(layouted_medal.color_end),
  ).rotate(45, get_resample(), expand=True)
  grad_h = int(GRADIENT_45DEG_WH / (1 + ratio))
  grad_w = int(ratio * grad_h)
  gradient = gradient.crop(
    (
      (gradient.width - grad_w) // 2,
      (gradient.height - grad_h) // 2,
      (gradient.width + grad_w) // 2,
      (gradient.height + grad_h) // 2,
    ),
  ).resize((medal_name_bg_width, medal_name_im.height), get_scale_resample())
  im.paste(gradient, (x + border, y + border))
  im.paste(medal_name_im, (x + border + padding, y + border), medal_name_im)

  x += medal_name_bg_width + border
  medal_level_bg_width = medal_level_im.width + padding * 2
  im.paste(
    (255, 255, 255),
    (x, y + border, x + medal_level_bg_width, y + border + medal_name_im.height),
  )
  im.paste(medal_level_im, (x + padding, y + border), medal_level_im)
  return im


def make_header(
  avatar: Image.Image,
  name: str,
  uid: int,
  fans: int,
  followings: int,
  matched_name: str,
  matched_count: int | None,
) -> Image.Image:
  name_im = render(name, "sans bold", 32)
  uid_im = render(str(uid), "sans", 28)
  info_im = render(
    f"<b>粉丝:</b> {fans} <b>关注:</b> {followings}",
    "sans",
    32,
    markup=True,
  )
  if matched_count is None:
    info2 = "??"
  else:
    ratio = 0 if followings == 0 else matched_count / followings * 100
    info2 = f"{matched_count} ({ratio:.2f}%)"
  info2_im = render(f"<b>{matched_name}:</b> {info2}", "sans", 32, markup=True)

  avatar = avatar.convert("RGB").resize((144, 144), get_scale_resample())
  circle(avatar)

  margin = 12
  padding = 6
  uid_width = uid_im.width + padding * 2
  im = Image.new(
    "RGB",
    (
      avatar.width + 32 + max(name_im.width + margin + uid_width, info_im.width, info2_im.width),
      max(avatar.height, name_im.height + info_im.height + info2_im.height),
    ),
    (255, 255, 255),
  )
  im.paste(avatar, (0, 0), avatar)

  x = avatar.width + 32
  im.paste(name_im, (x, 0), name_im)

  y = (name_im.height - uid_im.height) // 2
  rounded_im = Image.new("L", (uid_width * 2, uid_im.height * 2), 0)
  ImageDraw.Draw(rounded_im).rounded_rectangle(
    (0, 0, rounded_im.width - 1, rounded_im.height - 1),
    8,
    255,
  )
  rounded_im = rounded_im.resize((uid_width, uid_im.height), get_scale_resample())
  im.paste((221, 221, 221), (x + name_im.width + margin, y), rounded_im)
  im.paste(uid_im, (x + name_im.width + margin + padding, y), uid_im)

  y = name_im.height
  im.paste(info_im, (x, y), info_im)
  y += info_im.height
  im.paste(info2_im, (x, y), info2_im)
  return im


async def get_uids(provider: Provider) -> set[int]:
  config = CONFIG()
  cache = CACHE()
  provider_id = provider.get_id()
  item = cache.caches.get(provider_id)
  now = datetime.now()
  if not item or item.last_update < now - config.update_interval:
    uids = await provider.get_uids()
    cache.caches[provider_id] = CacheItem(last_update=now, uids=uids)
    CACHE.dump()
    return uids
  return item.uids


async def handle_bilibili_check(id_or_name: str, state: T_State) -> None:
  provider: Provider = state["provider"]
  uids = await get_uids(provider)

  cookie = get_cookie()
  headers = {
    "User-Agent": BROWSER_UA,
    # 2024-05-08: Cookie 为空时不能搜索，但任意非空字符串都可以搜索
    "Cookie": cookie or "SESSDATA=",
  }
  session = get_session()

  try:
    uid = int(id_or_name)
  except ValueError as e:
    async with session.get(
      SEARCH_API.format(encodeuri(id_or_name)),
      headers=headers,
      raise_for_status=True,
    ) as response:
      search_data = validate_result(await response.json(), SearchResult)
    if "result" not in search_data:
      await UniMessage(f"找不到 B 站用户：{id_or_name}").send()
      raise FinishedException from e
    uid = search_data["result"][0]["mid"]

  async with session.get(INFO_API.format(uid), headers=headers, raise_for_status=True) as resp:
    info_data = validate_result(await resp.json(), InfoResult)
  name = info_data["card"]["name"]
  fans = info_data["card"]["fans"]
  following = info_data["card"]["attention"]
  avatar = info_data["card"]["face"]

  following_list = list[User]()
  for pn in count(1):
    async with session.get(
      FOLLOW_API.format(vmid=uid, pn=pn),
      headers=headers,
      raise_for_status=True,
    ) as resp:
      follow_data = validate_biligame_result(await resp.json(), FollowingResult)
    following_list.extend(User(int(x["mid"]), x["uname"]) for x in follow_data["list"])
    if len(following_list) >= following or len(follow_data["list"]) < 50:
      break

  medals = None
  try:
    async with session.get(MEDAL_API.format(uid), headers=headers) as resp:
      medal_data = validate_result(await resp.json(), MedalResult)
    medals = {data["medal_info"]["target_id"]: data["medal_info"] for data in medal_data["list"]}
  except ApiError as e:
    if e.code != -101:
      raise

  avatar = await open_url(avatar)

  def make() -> ImageSeg:
    private = following != 0 and not following_list
    matched = [x for x in following_list if x.id in uids]
    matched_count = None if private else len(matched)
    header = make_header(avatar, name, uid, fans, following, provider.get_name(), matched_count)

    if not matched:
      if private:
        items = [render("关注列表不公开", "sans", 32)]
      else:
        items = [render("什么都查不到", "sans", 32)]
    else:
      items = []
      if len(following_list) < following:
        items.append(render(f"⚠️ 关注列表不全，仅查到 {len(matched)} 个", "sans", 32))
      if medals is None:
        if not cookie:
          items.append(render("⚠️ 未设置 Cookie，无法获取粉丝团信息", "sans", 32))
        else:
          items.append(render("⚠️ Cookie 过期或无效，无法获取粉丝团信息", "sans", 32))
        items.extend(make_list_item(x.name, x.id, None) for x in matched)
      else:
        items.extend(make_list_item(x.name, x.id, medals.get(x.id)) for x in matched)

    margin = 32
    gap = 16
    x_padding = 12
    y_padding = 6
    border = 2
    list_height = sum(im.height + y_padding * 2 for im in items) + border * 2
    im = Image.new(
      "RGB",
      (
        max(header.width, max(im.width + x_padding * 2 for im in items) + border * 2) + margin * 2,
        header.height + gap + list_height + margin * 2,
      ),
      (255, 255, 255),
    )
    im.paste(header, (margin, margin))

    y = margin + header.height + gap
    im.paste((238, 238, 238), (margin, y, im.width - margin, y + list_height))

    x = margin + 2
    y += 2
    for i, item in enumerate(items):
      item_height = item.height + y_padding * 2
      if i % 2 == 0:
        im.paste((255, 255, 255), (x, y, im.width - margin - border, y + item_height))
      else:
        im.paste((247, 247, 247), (x, y, im.width - margin - border, y + item_height))
      im.paste(item, (x + x_padding, y + y_padding), item)
      y += item_height

    return to_segment(im)

  await UniMessage(await run_sync(make)).send()


register(vtb)
try:
  from idhagnbot.plugins.bilibili_check import furry
except ImportError:
  pass
else:
  register(furry)
