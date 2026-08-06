from dataclasses import dataclass
from datetime import datetime, time
from typing import TypedDict, override
from zoneinfo import ZoneInfo

from arclet.alconna import Alconna, CommandMeta, Option, store_true
from arclet.entari import Element, Image, MessageChain, Plugin, Text, command
from arclet.letoderea import propagate
from entari_plugin_permission import require_permission  # entari: plugin
from pydantic import BaseModel, TypeAdapter
from satori.element import Br

from idhagnbot.http import BROWSER_UA, get_session
from idhagnbot.plugins.daily_push import register
from idhagnbot.plugins.daily_push.cache import DailyCache
from idhagnbot.plugins.daily_push.module import SimpleModule

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
            enable_prev=True,
            update_time=time(10, tzinfo=ZoneInfo("America/New_York")),
        )

    @override
    async def do_update(self) -> None:
        items = await get_free_assets()
        items.sort(key=lambda x: x.uid)
        cache = Cache(assets=items)
        with self.path.open("w") as f:
            f.write(cache.model_dump_json())

    def get(self) -> tuple[datetime, list[Asset]]:
        with self.date_path.open() as f:
            date = datetime.fromisoformat(f.read())
        with self.path.open() as f:
            cache = Cache.model_validate_json(f.read())
        return date, cache.assets

    def get_prev(self) -> tuple[datetime, list[Asset]] | None:
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
PLUGIN = Plugin.current()


@PLUGIN.collect
@register
class FabModule(SimpleModule):
    type = "fab"
    force: bool = False

    @override
    async def format(self) -> list[MessageChain]:
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
        message: MessageChain[Element] = MessageChain(Text("Fab 今天可以喜加一："))
        for item in items:
            text = f"{item.name}\n{URL_BASE}{item.uid}"
            message.extend([Br(), Text(text), Br(), Image(item.image)])
        return [message]


@command.on(
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
@propagate(require_permission("idhagnbot.fab", prompt=True))
async def handle_fab(*, no_cache: bool) -> str | MessageChain:
    if no_cache:
        await CACHE.update()
    else:
        await CACHE.ensure()
    _, items = CACHE.get()
    if not items:
        return "似乎没有可白嫖的资产"
    message = MessageChain()
    for item in items:
        text = f"{item.name}\n{URL_BASE}{item.uid}"
        if message:
            message.append(Br())
        message.extend([Text(text), Br(), Image(item.image)])
    return message
