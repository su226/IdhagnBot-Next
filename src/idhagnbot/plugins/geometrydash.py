from collections.abc import Iterable
from datetime import datetime, time
from typing import Literal, cast
from zoneinfo import ZoneInfo

import nonebot
from nonebot.typing import T_State
from pydantic import BaseModel

from idhagnbot.command import CommandBuilder
from idhagnbot.http import get_session
from idhagnbot.itertools import batched

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

SERVER = "https://www.boomlings.com/database"


class Level(BaseModel):
  id: int
  name: str
  downloads: int
  likes: int
  length: int
  stars: int
  coins: int
  daily: int
  demon: int
  author: str
  demon_tier: float | None = None
  has_image: bool = False

  @staticmethod
  def parse(data: str) -> "Level":
    level, _, _, author, *_ = data.split("#")
    data1 = dict(cast(Iterable[tuple[str, str]], batched(level.split(":"), 2)))
    return Level.model_validate(
      {
        "id": data1["1"],
        "name": data1["2"],
        "downloads": data1["10"],
        "likes": data1["14"],
        "length": data1["15"],
        "stars": data1["18"],
        "coins": data1["37"],
        "daily": data1["41"],
        "demon": data1["43"],
        "author": author.split(":")[1],
      },
    )

  def difficulty_name(self) -> str:
    if self.stars == 1:
      return "Auto"
    if self.stars == 2:
      return "Easy"
    if self.stars == 3:
      return "Normal"
    if self.stars in (4, 5):
      return "Hard"
    if self.stars in (6, 7):
      return "Harder"
    if self.stars in (8, 9):
      return "Insane"
    if self.stars == 10:
      if self.demon == 3:
        return "Easy Demon"
      if self.demon == 4:
        return "Medium Demon"
      if self.demon == 0:
        return "Hard Demon"
      if self.demon == 5:
        return "Insane Demon"
      if self.demon == 6:
        return "Extreme Demon"
    return "N/A"

  def length_name(self) -> str:
    if self.length == 0:
      return "Tiny"
    if self.length == 1:
      return "Short"
    if self.length == 2:
      return "Medium"
    if self.length == 3:
      return "Long"
    if self.length == 4:
      return "XL"
    return "Plat."

  def orbs(self) -> int:
    if self.stars == 2:
      return 50
    if self.stars == 3:
      return 75
    if self.stars == 4:
      return 125
    if self.stars == 5:
      return 175
    if self.stars == 6:
      return 225
    if self.stars == 7:
      return 275
    if self.stars == 8:
      return 350
    if self.stars == 9:
      return 425
    if self.stars == 10:
      return 500
    return 0

  def format(self) -> str:
    demon_tier = f" T{round(self.demon_tier)}" if self.demon_tier is not None else ""
    coins = f" {'🪙' * self.coins}" if self.coins else ""
    if self.daily > 200000:
      daily_id = f"Event #{self.daily - 200000}"
    elif self.daily > 100000:
      daily_id = f"Weekly #{self.daily - 100000}"
    else:
      daily_id = f"Daily #{self.daily}"
    return f"""\
"{self.name}" by {self.author}
Level #{self.id} {daily_id}
{self.difficulty_name()}{demon_tier} {self.stars}⭐{coins}
🕔{self.length_name()} ⬇️{self.downloads} 👍{self.likes} 🔮{self.orbs()}"""


class Cache(BaseModel):
  level: Level


class GeometryDashCache(DailyCache):
  def __init__(self, name: str, level_id: int) -> None:
    super().__init__(
      f"geometrydash_{name}.json",
      enable_prev=True,
      extra_files=[f"geometrydash_{name}.webp"],
      update_time=time(tzinfo=ZoneInfo("Europe/Berlin")),
    )
    self.image_path = self.path.with_suffix(".webp")
    self.level_id = level_id

  async def do_update(self) -> None:
    http = get_session()
    async with http.post(
      f"{SERVER}/downloadGJLevel22.php",
      skip_auto_headers=["User-Agent"],
      data={"secret": "Wmfd2893gb7", "levelID": self.level_id},
    ) as response:
      level = Level.parse(await response.text())
    async with http.get(f"https://levelthumbs.prevter.me/thumbnail/{level.id}") as response:
      if response.status == 200:
        with self.image_path.open("wb") as f:
          f.write(await response.read())
          level.has_image = True
    if level.stars == 10:
      async with http.get(f"https://gdladder.com/api/level/{level.id}") as response:
        data = await response.json()
        level.demon_tier = data.get("Rating")
    cache = Cache(level=level)
    with self.path.open("w") as f:
      f.write(cache.model_dump_json())

  def get(self) -> tuple[datetime, Level]:
    with self.date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with self.path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.level

  def get_prev(self) -> tuple[datetime, Level] | None:
    prev_path = self.path.with_suffix(".prev.json")
    prev_date_path = self.date_path.with_suffix(".prev.date")
    if not prev_path.exists() or not prev_date_path.exists():
      return None
    with prev_date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with prev_path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.level


DAILY_CACHE = GeometryDashCache("daily", -1)
WEEKLY_CACHE = GeometryDashCache("weekly", -2)
EVENT_CACHE = GeometryDashCache("event", -3)


@register("geometrydash")
class GeometryDashModule(SimpleModule):
  subtype: Literal["daily", "weekly", "event"] = "daily"
  force: bool = False

  async def format(self) -> list[UniMessage[Segment]]:
    if self.subtype == "daily":
      cache = DAILY_CACHE
    elif self.subtype == "weekly":
      cache = WEEKLY_CACHE
    else:
      cache = EVENT_CACHE
    await cache.ensure()
    _, level = cache.get()
    if not self.force:
      prev = cache.get_prev()
      if prev and level.id == prev[1].id:
        return []
    if level.daily > 200000:
      description = "event level"
    elif level.daily > 100000:
      description = "weekly demon"
    else:
      description = "daily level"
    message = UniMessage[Segment](Text(f"New {description}: {level.format()}"))
    if level.has_image:
      message += Image(path=cache.image_path)
    return [message]


geometrydash_daily = (
  CommandBuilder()
  .node("geometrydash.daily")
  .parser(
    Alconna(
      "几何冲刺daily",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询几何冲刺每日关卡"),
    ),
  )
  .state({"cache": DAILY_CACHE})
  .build()
)
geometrydash_weekly = (
  CommandBuilder()
  .node("geometrydash.weekly")
  .parser(
    Alconna(
      "几何冲刺weekly",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询几何冲刺每周恶魔"),
    ),
  )
  .state({"cache": WEEKLY_CACHE})
  .build()
)
geometrydash_event = (
  CommandBuilder()
  .node("geometrydash.event")
  .parser(
    Alconna(
      "几何冲刺event",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询几何冲刺活动关卡"),
    ),
  )
  .state({"cache": EVENT_CACHE})
  .build()
)


@geometrydash_daily.handle()
@geometrydash_weekly.handle()
@geometrydash_event.handle()
async def _(*, no_cache: bool, state: T_State) -> None:
  cache: GeometryDashCache = state["cache"]
  if no_cache:
    await cache.update()
  else:
    await cache.ensure()
  _, level = cache.get()
  message = UniMessage(Text(level.format()))
  if level.has_image:
    message += Image(path=cache.image_path)
  await message.send()
