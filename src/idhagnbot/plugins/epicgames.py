from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time, timezone
from enum import Enum
from functools import cached_property
from typing import Literal
from zoneinfo import ZoneInfo

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
  "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
  "?locale=zh-CN&country=CN&allowCountries=CN"
)
GAME_URL_BASE = "https://store.epicgames.com/zh-CN/p/"
BUNDLE_URL_BASE = "https://store.epicgames.com/zh-CN/bundles/"
DISCOUNT_FREE = {"discountType": "PERCENTAGE", "discountPercentage": 0}


class GameType(Enum):
  GAME = "GAME"
  ADD_ON = "ADD_ON"
  BUNDLE = "BUNDLE"
  OTHERS = "OTHERS"


@dataclass
class Game:
  start_date: datetime
  end_date: datetime
  title: str
  image: str
  slug: str
  type: GameType

  @cached_property
  def url(self) -> str:
    if not self.slug:
      return ""
    if self.type == GameType.BUNDLE:
      return BUNDLE_URL_BASE + self.slug
    return GAME_URL_BASE + self.slug


class ApiDiscountSetting(TypedDict):
  discountType: str
  discountPercentage: int


class ApiPromotionOffer(TypedDict):
  startDate: str | None
  endDate: str | None
  discountSetting: ApiDiscountSetting


class ApiPromotionOffers(TypedDict):
  promotionalOffers: list[ApiPromotionOffer]


class ApiPromotions(TypedDict):
  promotionalOffers: list[ApiPromotionOffers]
  upcomingPromotionalOffers: list[ApiPromotionOffers]


class ApiKeyImage(TypedDict):
  type: str
  url: str


class ApiMapping(TypedDict):
  pageType: str
  pageSlug: str


class ApiCatalogNs(TypedDict):
  mappings: list[ApiMapping] | None


class ApiCategory(TypedDict):
  path: str


class ApiElement(TypedDict):
  title: str
  productSlug: str | None
  urlSlug: str
  promotions: ApiPromotions | None
  keyImages: list[ApiKeyImage]
  catalogNs: ApiCatalogNs
  offerMappings: list[ApiMapping] | None
  offerType: Literal["BASE_GAME", "ADD_ON", "BUNDLE", "OTHERS"]
  categories: list[ApiCategory]


class ApiSearchStore(TypedDict):
  elements: list[ApiElement]


class ApiCatalog(TypedDict):
  searchStore: ApiSearchStore


class ApiData(TypedDict):
  Catalog: ApiCatalog


class ApiResult(TypedDict):
  data: ApiData


ApiResultAdapter = TypeAdapter(ApiResult)


def iter_promotions(game: ApiElement) -> Iterable[ApiPromotionOffer]:
  if game["promotions"]:
    for i in game["promotions"]["promotionalOffers"]:
      yield from i["promotionalOffers"]
    for i in game["promotions"]["upcomingPromotionalOffers"]:
      yield from i["promotionalOffers"]


def get_image(game: ApiElement) -> str:
  for i in game["keyImages"]:
    if i["type"] in ("DieselStoreFrontWide", "OfferImageWide"):
      return i["url"]
  return ""


def iter_mappings(game: ApiElement) -> Iterable[ApiMapping]:
  if game["catalogNs"]["mappings"]:
    yield from game["catalogNs"]["mappings"]
  if game["offerMappings"]:
    yield from game["offerMappings"]


def get_slug(game: ApiElement) -> str:
  for i in iter_mappings(game):
    if i["pageType"] == "offer":
      return i["pageSlug"]
  for i in iter_mappings(game):
    if i["pageType"] == "productHome":
      return i["pageSlug"]
  return game["productSlug"] or game["urlSlug"]


def get_type(game: ApiElement) -> GameType:
  if game["offerType"] == "ADD_ON":
    return GameType.ADD_ON
  if game["offerType"] == "BUNDLE":
    return GameType.BUNDLE
  if game["offerType"] == "OTHERS":
    for category in game["categories"]:
      if category["path"] == "bundles":
        return GameType.BUNDLE
    return GameType.OTHERS
  return GameType.GAME


async def get_free_games() -> list[Game]:
  async with get_session().get(API) as response:
    data = ApiResultAdapter.validate_python(await response.json())
  result = list[Game]()
  now_date = datetime.now(timezone.utc)
  for game in data["data"]["Catalog"]["searchStore"]["elements"]:
    for i in iter_promotions(game):
      # Python不支持Z结束，须替换成+00:00
      if i["startDate"] is None or i["endDate"] is None:
        continue
      start_date = datetime.fromisoformat(i["startDate"].replace("Z", "+00:00"))
      end_date = datetime.fromisoformat(i["endDate"].replace("Z", "+00:00"))
      if i["discountSetting"] == DISCOUNT_FREE and start_date < end_date and now_date < end_date:
        slug = get_slug(game)
        result.append(
          Game(
            start_date=start_date,
            end_date=end_date,
            title=game["title"],
            image=get_image(game),
            slug="" if slug == "[]" else slug,
            type=get_type(game),
          ),
        )
        break
  return result


class Cache(BaseModel):
  games: list[Game]


class EpicGamesCache(DailyCache):
  def __init__(self) -> None:
    super().__init__(
      "epicgames.json",
      enable_prev=True,
      update_time=time(11, tzinfo=ZoneInfo("America/New_York")),
    )

  @override
  async def do_update(self) -> None:
    games = await get_free_games()
    games.sort(key=lambda x: (x.end_date, x.slug))
    cache = Cache(games=games)
    with self.path.open("w") as f:
      f.write(cache.model_dump_json())

  def get(self) -> tuple[datetime, list[Game]]:
    with self.date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with self.path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.games

  def get_prev(self) -> tuple[datetime, list[Game]] | None:
    prev_path = self.path.with_suffix(".prev.json")
    prev_date_path = self.date_path.with_suffix(".prev.date")
    if not prev_path.exists() or not prev_date_path.exists():
      return None
    with prev_date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with prev_path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.games


CACHE = EpicGamesCache()


@register("epicgames")
class EpicGamesModule(SimpleModule):
  force: bool = False

  @override
  async def format(self) -> list[UniMessage[Segment]]:
    await CACHE.ensure()
    now_date = datetime.now(timezone.utc)
    _, games = CACHE.get()
    games = [game for game in games if now_date > game.start_date]
    if not self.force:
      prev = CACHE.get_prev()
      if prev:
        prev_date, prev_games = prev
        prev_slugs = {game.slug for game in prev_games if prev_date > game.start_date}
        games = [game for game in games if game.slug not in prev_slugs]
    if not games:
      return []
    message = UniMessage[Segment](Text("Epic Games 今天可以喜加一："))
    for game in games:
      end_str = game.end_date.astimezone().strftime("%Y-%m-%d %H:%M")
      text = f"{game.title}，截止到 {end_str}"
      if game.url:
        text += f"\n{game.url}"
      message.extend([Text.br(), Text(text), Text.br(), Image(url=game.image)])
    return [message]


epicgames = (
  CommandBuilder()
  .node("epicgames")
  .parser(
    Alconna(
      "epicgames",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询 Epic Games 免费游戏"),
    ),
  )
  .build()
)


@epicgames.handle()
async def handle_epicgames(*, no_cache: bool) -> None:
  if no_cache:
    await CACHE.update()
  else:
    await CACHE.ensure()
  _, games = CACHE.get()
  if not games:
    await epicgames.finish("似乎没有可白嫖的游戏")
  games.sort(key=lambda x: x.end_date)
  now_date = datetime.now(timezone.utc)
  message = UniMessage()
  for game in games:
    end_str = game.end_date.astimezone().strftime("%Y-%m-%d %H:%M")
    if now_date > game.start_date:
      text = f"{game.title} 目前免费，截止到 {end_str}"
    else:
      start_str = game.start_date.astimezone().strftime("%Y-%m-%d %H:%M")
      text = f"{game.title} 将在 {start_str} 免费，截止到 {end_str}"
    if game.url:
      text += f"\n{game.url}"
    if message:
      message.append(Text.br())
    message.extend(
      [
        Text(text),
        Text.br(),
        Image(url=game.image),
      ],
    )
  await message.send()
