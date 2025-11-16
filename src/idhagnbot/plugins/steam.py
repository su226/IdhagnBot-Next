import enum
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional, TypedDict

import nonebot
from pydantic import BaseModel, TypeAdapter

from idhagnbot.command import CommandBuilder
from idhagnbot.config import SharedConfig
from idhagnbot.http import get_session

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
from idhagnbot.plugins.daily_push.module import SimpleModule, register


class Config(BaseModel):
  proxy: str = ""


CONFIG = SharedConfig("steam", Config)
API = "https://store.steampowered.com/search/results/?query&maxprice=free&specials=1&infinite=1"
URL_BASE = "https://store.steampowered.com/app/"


class ApiResult(TypedDict):
  results_html: str


ApiResultAdapter = TypeAdapter(ApiResult)


@dataclass
class Game:
  appid: int
  name: str
  image: str


class ParserMode(enum.Enum):
  NONE = enum.auto()
  NAME = enum.auto()


class Parser(HTMLParser):
  def __init__(self) -> None:
    super().__init__()
    self.games: list[Game] = []
    self.mode = ParserMode.NONE

  def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
    if tag == "a":
      self.game = Game(0, "", "")
      for key, value in attrs:
        if key == "data-ds-appid":
          if value:
            self.game.appid = int(value)
          break
    elif tag == "img":
      for key, value in attrs:
        if key == "src":
          if value:
            self.game.image = value
          break
    else:
      classes: set[str] = set()
      for key, value in attrs:
        if key == "class":
          if value:
            classes.update(value.split())
          break
      if "title" in classes:
        self.mode = ParserMode.NAME

  def handle_endtag(self, tag: str) -> None:
    self.mode = ParserMode.NONE
    if tag == "a":
      self.games.append(self.game)

  def handle_data(self, data: str) -> None:
    if self.mode == ParserMode.NAME:
      self.game.name = data

  @staticmethod
  def parse(data: str) -> list[Game]:
    parser = Parser()
    parser.feed(data)
    parser.close()
    return parser.games


async def get_free_games() -> list[Game]:
  async with get_session().get(API, proxy=CONFIG().proxy) as response:
    data = ApiResultAdapter.validate_python(await response.json())
  return Parser.parse(data["results_html"])


class Cache(BaseModel):
  items: list[Game]


class SteamCache(DailyCache):
  def __init__(self) -> None:
    super().__init__("steam.json", True)

  async def do_update(self) -> None:
    items = await get_free_games()
    cache = Cache(items=items)
    with self.path.open("w") as f:
      f.write(cache.model_dump_json())

  def get(self) -> tuple[datetime, list[Game]]:
    with self.date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with self.path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.items

  def get_prev(self) -> Optional[tuple[datetime, list[Game]]]:
    prev_path = self.path.with_suffix(".prev.json")
    prev_date_path = self.date_path.with_suffix(".prev.date")
    if not prev_path.exists() or not prev_date_path.exists():
      return None
    with prev_date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with prev_path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.items


CACHE = SteamCache()


@register("steam")
class SteamModule(SimpleModule):
  force: bool = False

  async def format(self) -> list[UniMessage[Segment]]:
    await CACHE.ensure()
    _, items = CACHE.get()
    if not self.force:
      prev = CACHE.get_prev()
      if prev:
        _, prev_items = prev
        prev_slugs = {item.appid for item in prev_items}
        items = [item for item in items if item.appid not in prev_slugs]
    if not items:
      return []
    message = UniMessage[Segment](Text("Steam 今天可以喜加一："))
    for item in items:
      text = f"{item.name}\n{URL_BASE}{item.appid}"
      message.extend([Text.br(), Text(text), Text.br(), Image(url=item.image)])
    return [message]


steam = (
  CommandBuilder()
  .node("steam")
  .parser(
    Alconna(
      "steam",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询 Steam 免费游戏"),
    ),
  )
  .build()
)


@steam.handle()
async def _(no_cache: bool) -> None:
  if no_cache:
    await CACHE.update()
  else:
    await CACHE.ensure()
  _, items = CACHE.get()
  if not items:
    await steam.finish("似乎没有可白嫖的游戏")
  message = UniMessage()
  for item in items:
    text = f"{item.name}\n{URL_BASE}{item.appid}"
    if message:
      message.append(Text.br())
    message.extend([Text(text), Text.br(), Image(url=item.image)])
  await message.send()
