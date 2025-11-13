from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional, TypedDict
from zoneinfo import ZoneInfo

import nonebot
from pydantic import BaseModel, TypeAdapter

from idhagnbot.command import CommandBuilder
from idhagnbot.http import BROWSER_UA, get_session

nonebot.require("nonebot_plugin_alconna")
nonebot.require("idhagnbot.plugins.daily_push")
from nonebot_plugin_alconna import (
  Alconna,
  CommandMeta,
  Image,
  Option,
  Segment,
  Text,
  UniMessage,
  store_true,
)

from idhagnbot.plugins.daily_push.cache import DailyCache
from idhagnbot.plugins.daily_push.module import Module, ModuleConfig, register

API = "https://www.fab.com/i/blades/free_content_blade"
HEADERS = {"Accept-Language": "zh-CN", "User-Agent": BROWSER_UA, "Priority": "u=0, i"}
URL_BASE = "https://www.fab.com/zh-cn/listings/"


class ApiThumbnail(TypedDict):
  mediaUrl: str


class ApiListing(TypedDict):
  title: str
  thumbnails: list[ApiThumbnail]
  uid: str


class ApiTile(TypedDict):
  listing: ApiListing


class ApiResult(TypedDict):
  tiles: list[ApiTile]


ApiResultAdapter = TypeAdapter(ApiResult)


@dataclass
class Asset:
  uid: str
  name: str
  image: str


async def get_free_assets() -> list[Asset]:
  async with get_session().get(API, headers=HEADERS) as response:
    data = ApiResultAdapter.validate_python(await response.json())
  return [
    Asset(
      tile["listing"]["uid"],
      tile["listing"]["title"],
      tile["listing"]["thumbnails"][0]["mediaUrl"],
    )
    for tile in data["tiles"]
  ]


class Cache(BaseModel):
  assets: list[Asset]


class FabCache(DailyCache):
  def __init__(self) -> None:
    super().__init__(
      "fab.json",
      True,
      update_time=time(10, tzinfo=ZoneInfo("America/New_York")),
    )

  async def do_update(self) -> None:
    games = await get_free_assets()
    games.sort(key=lambda x: x.uid)
    with self.path.open("w") as f:
      f.write(Cache(assets=games).model_dump_json())

  def get(self) -> tuple[datetime, list[Asset]]:
    with self.date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with self.path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.assets

  def get_prev(self) -> Optional[tuple[datetime, list[Asset]]]:
    prev_path = self.path.with_suffix(".prev.json")
    prev_date_path = self.date_path.with_suffix(".prev.date")
    if not prev_path.exists() or not prev_date_path.exists():
      return None
    with prev_date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with prev_path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.assets


CACHE = FabCache()


class FabModule(Module):
  def __init__(self, force: bool) -> None:
    self.force = force

  async def format(self) -> list[UniMessage[Segment]]:
    await CACHE.ensure()
    _, items = CACHE.get()
    if not self.force:
      prev = CACHE.get_prev()
      if prev:
        _, prev_items = prev
        prev_uids = {item.uid for item in prev_items}
        items = [item for item in items if item.uid not in prev_uids]
    if not items:
      return []
    message = UniMessage[Segment](Text("Fab 今天可以喜加一："))
    for item in items:
      text = f"{item.name}\n{URL_BASE}{item.uid}"
      message.extend([Text.br(), Text(text), Text.br(), Image(url=item.image)])
    return [message]


@register("fab")
class FabModuleConfig(ModuleConfig):
  force: bool = False

  def create_module(self) -> Module:
    return FabModule(self.force)


fab = (
  CommandBuilder()
  .node("fab")
  .parser(
    Alconna(
      "fab",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询 Fab 免费资产"),
    ),
  )
  .build()
)


@fab.handle()
async def _(no_cache: bool) -> None:
  if no_cache:
    await CACHE.update()
  else:
    await CACHE.ensure()
  _, items = CACHE.get()
  if not items:
    await fab.finish("似乎没有可白嫖的资产")
  message = UniMessage()
  for item in items:
    text = f"{item.name}\n{URL_BASE}{item.uid}"
    if message:
      message.append(Text.br())
    message.extend([Text(text), Text.br(), Image(url=item.image)])
  await message.send()
