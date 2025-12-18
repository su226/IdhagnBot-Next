from dataclasses import dataclass
from datetime import datetime

import nonebot
from pydantic import BaseModel, TypeAdapter
from typing_extensions import TypedDict, override

from idhagnbot.command import CommandBuilder
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

API = (
  "https://catalog.gog.com/v1/catalog?limit=48&price=between%3A0%2C0&order=desc%3Atrending"
  "&discounted=eq%3Atrue&productType=in%3Agame%2Cpack%2Cdlc%2Cextras&page=1&countryCode=CN"
  "&locale=zh-Hans&currencyCode=CNY"
)
URL_BASE = "https://www.gog.com/zh/game/"


class ApiProduct(TypedDict):
  slug: str
  title: str
  coverHorizontal: str


class ApiResult(TypedDict):
  products: list[ApiProduct]


ApiResultAdapter = TypeAdapter(ApiResult)


@dataclass
class Game:
  slug: str
  name: str
  image: str


async def get_free_games() -> list[Game]:
  async with get_session().get(API) as response:
    data = ApiResultAdapter.validate_python(await response.json())
  return [
    Game(
      slug=product["slug"],
      name=product["title"],
      image=product["coverHorizontal"],
    )
    for product in data["products"]
  ]


class Cache(BaseModel):
  items: list[Game]


class GogCache(DailyCache):
  def __init__(self) -> None:
    super().__init__("gog.json", enable_prev=True)

  @override
  async def do_update(self) -> None:
    games = await get_free_games()
    cache = Cache(items=games)
    with self.path.open("w") as f:
      f.write(cache.model_dump_json())

  def get(self) -> tuple[datetime, list[Game]]:
    with self.date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with self.path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.items

  def get_prev(self) -> tuple[datetime, list[Game]] | None:
    prev_path = self.path.with_suffix(".prev.json")
    prev_date_path = self.date_path.with_suffix(".prev.date")
    if not prev_path.exists() or not prev_date_path.exists():
      return None
    with prev_date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with prev_path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.items


CACHE = GogCache()


@register("gog")
class GogModule(SimpleModule):
  force: bool = False

  @override
  async def format(self) -> list[UniMessage[Segment]]:
    await CACHE.ensure()
    _, items = CACHE.get()
    if not self.force:
      prev = CACHE.get_prev()
      if prev:
        _, prev_items = prev
        prev_slugs = {item.slug for item in prev_items}
        items = [item for item in items if item.slug not in prev_slugs]
    if not items:
      return []
    message = UniMessage[Segment](Text("GOG 今天可以喜加一："))
    for item in items:
      text = f"{item.name}\n{URL_BASE}{item.slug}"
      message.extend([Text.br(), Text(text), Text.br(), Image(url=item.image)])
    return [message]


gog = (
  CommandBuilder()
  .node("gog")
  .parser(
    Alconna(
      "gog",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询 GOG 免费游戏"),
    ),
  )
  .build()
)


@gog.handle()
async def _(*, no_cache: bool) -> None:
  if no_cache:
    await CACHE.update()
  else:
    await CACHE.ensure()
  _, items = CACHE.get()
  if not items:
    await gog.finish("似乎没有可白嫖的游戏")
  message = UniMessage()
  for item in items:
    text = f"{item.name}\n{URL_BASE}{item.slug}"
    if message:
      message.append(Text.br())
    message.extend([Text(text), Text.br(), Image(url=item.image)])
  await message.send()
