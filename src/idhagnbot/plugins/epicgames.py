from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import nonebot
from pydantic import BaseModel

from idhagnbot.command import CommandBuilder
from idhagnbot.third_party import epicgames as api

nonebot.require("nonebot_plugin_alconna")
nonebot.require("idhagnbot.plugins.daily_push")
from nonebot_plugin_alconna import Alconna, CommandMeta, Option, store_true
from nonebot_plugin_alconna.uniseg import Image, Segment, Text, UniMessage

from idhagnbot.plugins.daily_push.cache import DailyCache
from idhagnbot.plugins.daily_push.module import Module, ModuleConfig, register


class Cache(BaseModel):
  games: list[api.Game]


class EpicGamesCache(DailyCache):
  def __init__(self) -> None:
    super().__init__(
      "epicgames.json",
      True,
      update_time=time(11, tzinfo=ZoneInfo("America/New_York")),
    )

  async def do_update(self) -> None:
    games = await api.get_free_games()
    games.sort(key=lambda x: (x.end_date, x.slug))
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


CACHE = EpicGamesCache()


class EpicGamesModule(Module):
  def __init__(self, force: bool) -> None:
    self.force = force

  async def format(self) -> list[UniMessage[Segment]]:
    await CACHE.ensure()
    now_date = datetime.now(timezone.utc)
    games = [game for game in CACHE.get() if now_date > game.start_date]
    if not self.force:
      prev_date, prev_games = CACHE.get_prev()
      prev_slugs = {game.slug for game in prev_games if prev_date > game.start_date}
      games = [game for game in games if game.slug not in prev_slugs]
    if not games:
      return []
    message = UniMessage[Segment](Text("Epic Games 今天可以喜加一："))
    for game in games:
      end_str = game.end_date.astimezone().strftime("%Y-%m-%d %H:%M")
      text = f"\n{game.title}，截止到 {end_str}\n{api.URL_BASE}{game.slug}\n"
      message.extend([Text(text), Image(url=game.image)])
    return [message]


@register("epicgames")
class EpicGamesModuleConfig(ModuleConfig):
  force: bool = False

  def create_module(self) -> Module:
    return EpicGamesModule(self.force)


epicgames = (
  CommandBuilder()
  .node("epicgames")
  .parser(Alconna(
    "epicgames",
    Option("--no-cache", dest="no_cache", action=store_true, default=False, help_text="禁用缓存"),
    meta=CommandMeta("查询 Epic Games 免费游戏"),
  ))
  .build()
)


@epicgames.handle()
async def handle_epicgames(no_cache: bool) -> None:
  if no_cache:
    await CACHE.update()
  else:
    await CACHE.ensure()
  games = CACHE.get()
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
    if message:
      text = "\n" + text
    message.extend(
      [
        Text(text + f"\n{api.URL_BASE}{game.slug}\n"),
        Image(url=game.image),
      ],
    )
  await message.send()
