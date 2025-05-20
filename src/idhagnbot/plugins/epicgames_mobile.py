from datetime import datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import nonebot
from nonebot.typing import T_State
from pydantic import BaseModel

from idhagnbot.command import CommandBuilder
from idhagnbot.third_party import epicgames_mobile as api

nonebot.require("nonebot_plugin_alconna")
nonebot.require("idhagnbot.plugins.daily_push")
from nonebot_plugin_alconna import Alconna, CommandMeta, Option, store_true
from nonebot_plugin_alconna.uniseg import Image, Segment, Text, UniMessage

from idhagnbot.plugins.daily_push.cache import DailyCache
from idhagnbot.plugins.daily_push.module import Module, ModuleConfig, register


class Cache(BaseModel):
  games: list[api.Game]


class EpicGamesMobileCache(DailyCache):
  def __init__(self, platform: Literal["android", "ios"]) -> None:
    super().__init__(
      f"epicgames_{platform}.json",
      True,
      update_time=time(11, tzinfo=ZoneInfo("America/New_York")),
    )
    self.platform: Literal["android", "ios"] = platform

  async def do_update(self) -> None:
    games = await api.get_free_games(self.platform)
    games.sort(key=lambda x: (x.end_date, x.name))
    model = Cache(games=games)
    with self.path.open("w") as f:
      f.write(model.model_dump_json())

  def get(self) -> list[api.Game]:
    with self.path.open() as f:
      data = Cache.model_validate_json(f.read())
    return data.games

  def get_prev(self) -> tuple[datetime, list[api.Game]]:
    prev_path = self.path.with_suffix(".prev.json")
    prev_date_path = self.date_path.with_suffix(".prev.date")
    if not prev_path.exists() or not prev_date_path.exists():
      return datetime(1, 1, 1, tzinfo=timezone.utc), []
    with prev_date_path.open() as f:
      prev_date = datetime.fromisoformat(f.read())
    with prev_path.open() as f:
      data = Cache.model_validate_json(f.read())
    return prev_date, data.games


ANDROID_CACHE = EpicGamesMobileCache("android")
IOS_CACHE = EpicGamesMobileCache("ios")


class EpicGamesMobileModule(Module):
  def __init__(self, cache: EpicGamesMobileCache, force: bool) -> None:
    self.cache = cache
    self.force = force

  async def format(self) -> list[UniMessage[Segment]]:
    await self.cache.ensure()
    now_date = datetime.now(timezone.utc)
    games = [game for game in self.cache.get() if now_date > game.start_date]
    if not self.force:
      prev_date, prev_games = self.cache.get_prev()
      prev_names = {game.name for game in prev_games if prev_date > game.start_date}
      games = [game for game in games if game.name not in prev_names]
    if not games:
      return []
    platform = "安卓" if self.cache.platform == "android" else "iOS"
    message = UniMessage[Segment](Text(f"Epic Games {platform}今天可以喜加一："))
    for game in games:
      end_str = game.end_date.astimezone().strftime("%Y-%m-%d %H:%M")
      text = f"\n{game.name}，截止到 {end_str}\n"
      message.extend([Text(text), Image(url=game.image)])
    return [message]


@register("epicgames_mobile")
class EpicGamesAndroidModuleConfig(ModuleConfig):
  platform: Literal["android", "ios"]
  force: bool = False

  def create_module(self) -> Module:
    cache = ANDROID_CACHE if self.platform == "android" else IOS_CACHE
    return EpicGamesMobileModule(cache, self.force)


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
  games = cache.get()
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
      text = "\n" + text
    message.extend([Text(text), Image(url=game.image)])
  await message.send()
