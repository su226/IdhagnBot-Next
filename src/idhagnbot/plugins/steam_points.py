from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import TypedDict
from zoneinfo import ZoneInfo

import nonebot
from pydantic import BaseModel, TypeAdapter
from typing_extensions import NotRequired

from idhagnbot.command import CommandBuilder
from idhagnbot.http import get_session

nonebot.require("nonebot_plugin_alconna")
nonebot.require("idhagnbot.plugins.daily_push")
from nonebot_plugin_alconna import Alconna, CommandMeta, Option, store_true
from nonebot_plugin_alconna.uniseg import Image, Segment, Text, UniMessage

from idhagnbot.plugins.daily_push.cache import DailyCache
from idhagnbot.plugins.daily_push.module import Module, ModuleConfig, register

API = (
  "https://api.steampowered.com/ILoyaltyRewardsService/QueryRewardItems/v1/"
  "?language=schinese&count=1000"
)
URL_BASE = "https://store.steampowered.com/points/shop/reward/"


class ApiCommunityItemData(TypedDict):
  item_title: str
  item_image_large: NotRequired[str]


class ApiDefinition(TypedDict):
  appid: int
  defid: int
  type: int
  point_cost: str
  community_item_data: ApiCommunityItemData
  bundle_discount: int


class ApiResponse(TypedDict):
  definitions: list[ApiDefinition]


class ApiResult(TypedDict):
  response: ApiResponse


ApiResultAdapter = TypeAdapter(ApiResult)


@dataclass
class Item:
  defid: int
  name: str
  image: str


async def get_free_items() -> list[Item]:
  async with get_session().get(API) as response:
    result = ApiResultAdapter.validate_python(await response.json())
  items = list[Item]()
  for item in result["response"]["definitions"]:
    free = item["bundle_discount"] == 100 if item["type"] == 6 else item["point_cost"] == "0"
    if free:
      items.append(
        Item(
          item["defid"],
          item["community_item_data"]["item_title"],
          (
            f"https://shared.akamai.steamstatic.com/community_assets/images/items/"
            f"{item['appid']}/{item['community_item_data']['item_image_large']}"
          )
          if "item_image_large" in item["community_item_data"]
          else "",
        ),
      )
  return items


class Cache(BaseModel):
  items: list[Item]


class SteamPointsCache(DailyCache):
  def __init__(self) -> None:
    super().__init__(
      "steam_points.json",
      True,
      update_time=time(12, tzinfo=ZoneInfo("America/Los_Angeles")),
    )

  async def do_update(self) -> None:
    items = await get_free_items()
    model = Cache(items=items)
    with self.path.open("w") as f:
      f.write(model.model_dump_json())

  def get(self) -> list[Item]:
    with self.path.open() as f:
      data = Cache.model_validate_json(f.read())
    return data.items

  def get_prev(self) -> tuple[datetime, list[Item]]:
    prev_path = self.path.with_suffix(".prev.json")
    prev_date_path = self.date_path.with_suffix(".prev.date")
    if not prev_path.exists() or not prev_date_path.exists():
      return datetime(1, 1, 1, tzinfo=timezone.utc), []
    with prev_date_path.open() as f:
      prev_date = datetime.fromisoformat(f.read())
    with prev_path.open() as f:
      data = Cache.model_validate_json(f.read())
    return prev_date, data.items


CACHE = SteamPointsCache()


class SteamPointsModule(Module):
  def __init__(self, force: bool) -> None:
    self.force = force

  async def format(self) -> list[UniMessage[Segment]]:
    await CACHE.ensure()
    items = CACHE.get()
    if not self.force:
      _, prev_items = CACHE.get_prev()
      prev_defids = {item.defid for item in prev_items}
      items = [item for item in items if item.defid not in prev_defids]
    if not items:
      return []
    message = UniMessage[Segment](Text("Steam 点数商店今天可以喜加一："))
    for item in items:
      text = f"\n{item.name}\n{URL_BASE}{item.defid}\n"
      message.extend([Text(text), Image(url=item.image)])
    return [message]


@register("steam_points")
class SteamPointsModuleConfig(ModuleConfig):
  force: bool = False

  def create_module(self) -> Module:
    return SteamPointsModule(self.force)


steam_points = (
  CommandBuilder()
  .node("steam_points")
  .parser(
    Alconna(
      "steam点数商店",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("查询 Steam 点数商店免费物品"),
    ),
  )
  .build()
)


@steam_points.handle()
async def handle_epicgames_android(no_cache: bool) -> None:
  if no_cache:
    await CACHE.update()
  else:
    await CACHE.ensure()
  items = CACHE.get()
  if not items:
    await steam_points.finish("似乎没有可白嫖的物品")
  message = UniMessage()
  for item in items:
    text = f"{item.name}\n{URL_BASE}{item.defid}"
    if message:
      message.append(Text.br())
    message.extend([Text(text), Text.br(), Image(url=item.image)])
  await message.send()
