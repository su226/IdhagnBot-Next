from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo

import nonebot
from nonebot.typing import T_State
from pydantic import BaseModel, TypeAdapter
from typing_extensions import NotRequired, TypedDict

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
from idhagnbot.plugins.daily_push.module import SimpleModule, register

API = (
  "https://egs-platform-service.store.epicgames.com/api/v2/public/discover/home"
  "?count=10&country=CN&locale=zh-CN&platform={platform}&start=0&store=EGS"
)


class ApiMediaItem(TypedDict):
  imageSrc: str


class ApiMedia(TypedDict):
  card16x9: ApiMediaItem


class ApiDiscount(TypedDict):
  discountAmountDisplay: str
  discountEndDate: str


class ApiPurchase(TypedDict):
  purchaseStateEffectiveDate: str
  discount: NotRequired[ApiDiscount]


class ApiContent(TypedDict):
  title: str
  media: ApiMedia
  purchase: list[ApiPurchase]


class ApiOffer(TypedDict):
  content: ApiContent


class ApiData(TypedDict):
  offers: list[ApiOffer]
  type: str


class ApiResult(TypedDict):
  data: list[ApiData]


ApiResultAdapter = TypeAdapter(ApiResult)


@dataclass
class Game:
  start_date: datetime
  end_date: datetime
  name: str
  image: str


async def get_free_games(platform: Literal["android", "ios"]) -> list[Game]:
  async with get_session().get(
    API.format(platform=platform),
    headers={"User-Agent": BROWSER_UA},
  ) as response:
    data = ApiResultAdapter.validate_python(await response.json())
  for topic in data["data"]:
    if topic["type"] == "freeGame":
      offers = topic["offers"]
      break
  else:
    return []
  games: list[Game] = []
  now_date = datetime.now(timezone.utc)
  for offer in offers:
    for purchase in offer["content"]["purchase"]:
      if "discount" in purchase and purchase["discount"]["discountAmountDisplay"] == "-100%":
        start_date = purchase["purchaseStateEffectiveDate"]
        end_date = purchase["discount"]["discountEndDate"]
        start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        if start_date < end_date and now_date < end_date:
          games.append(
            Game(
              start_date=start_date,
              end_date=end_date,
              name=offer["content"]["title"],
              image=offer["content"]["media"]["card16x9"]["imageSrc"],
            ),
          )
          break
  return games


class Cache(BaseModel):
  games: list[Game]


class EpicGamesMobileCache(DailyCache):
  def __init__(self, platform: Literal["android", "ios"]) -> None:
    super().__init__(
      f"epicgames_{platform}.json",
      True,
      update_time=time(11, tzinfo=ZoneInfo("America/New_York")),
    )
    self.platform: Literal["android", "ios"] = platform

  async def do_update(self) -> None:
    games = await get_free_games(self.platform)
    games.sort(key=lambda x: (x.end_date, x.name))
    cache = Cache(games=games)
    with self.path.open("w") as f:
      f.write(cache.model_dump_json())

  def get(self) -> tuple[datetime, list[Game]]:
    with self.date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with self.path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.games

  def get_prev(self) -> Optional[tuple[datetime, list[Game]]]:
    prev_path = self.path.with_suffix(".prev.json")
    prev_date_path = self.date_path.with_suffix(".prev.date")
    if not prev_path.exists() or not prev_date_path.exists():
      return None
    with prev_date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with prev_path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.games


ANDROID_CACHE = EpicGamesMobileCache("android")
IOS_CACHE = EpicGamesMobileCache("ios")


@register("epicgames_mobile")
class EpicGamesMobileModule(SimpleModule):
  platform: Literal["android", "ios"]
  force: bool = False

  async def format(self) -> list[UniMessage[Segment]]:
    cache = ANDROID_CACHE if self.platform == "android" else IOS_CACHE
    await cache.ensure()
    now_date = datetime.now(timezone.utc)
    _, games = cache.get()
    games = [game for game in games if now_date > game.start_date]
    if not self.force:
      prev = cache.get_prev()
      if prev:
        prev_date, prev_games = prev
        prev_names = {game.name for game in prev_games if prev_date > game.start_date}
        games = [game for game in games if game.name not in prev_names]
    if not games:
      return []
    platform = "安卓" if self.platform == "android" else "iOS"
    message = UniMessage[Segment](Text(f"Epic Games {platform}今天可以喜加一："))
    for game in games:
      end_str = game.end_date.astimezone().strftime("%Y-%m-%d %H:%M")
      text = f"{game.name}，截止到 {end_str}"
      message.extend([Text.br(), Text(text), Text.br(), Image(url=game.image)])
    return [message]


epicgames_android = (
  CommandBuilder()
  .node("epicgames_mobile.android")
  .parser(
    Alconna(
      "epicgames_安卓",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询 Epic Games 安卓免费游戏"),
    ),
  )
  .state({"cache": ANDROID_CACHE})
  .build()
)
epicgames_ios = (
  CommandBuilder()
  .node("epicgames_mobile.ios")
  .parser(
    Alconna(
      "epicgames_ios",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询 Epic Games iOS 免费游戏"),
    ),
  )
  .state({"cache": IOS_CACHE})
  .build()
)


@epicgames_android.handle()
@epicgames_ios.handle()
async def handle_epicgames_android(no_cache: bool, state: T_State) -> None:
  cache: EpicGamesMobileCache = state["cache"]
  if no_cache:
    await cache.update()
  else:
    await cache.ensure()
  _, games = cache.get()
  if not games:
    await epicgames_android.finish("似乎没有可白嫖的游戏")
  games.sort(key=lambda x: x.end_date)
  now_date = datetime.now(timezone.utc)
  message = UniMessage()
  for game in games:
    end_str = game.end_date.astimezone().strftime("%Y-%m-%d %H:%M")
    if now_date > game.start_date:
      text = f"{game.name} 目前免费，截止到 {end_str}"
    else:
      start_str = game.start_date.astimezone().strftime("%Y-%m-%d %H:%M")
      text = f"{game.name} 将在 {start_str} 免费，截止到 {end_str}"
    if message:
      message.append(Text.br())
    message.extend([Text(text), Text.br(), Image(url=game.image)])
  await message.send()
