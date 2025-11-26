from datetime import date, datetime
from html.parser import HTMLParser
from io import StringIO

import nonebot
from pydantic import BaseModel, TypeAdapter
from typing_extensions import TypedDict

from idhagnbot.command import CommandBuilder
from idhagnbot.http import get_session

nonebot.require("nonebot_plugin_alconna")
nonebot.require("idhagnbot.plugins.daily_push")
from nonebot_plugin_alconna import (
  Alconna,
  CommandMeta,
  Option,
  Segment,
  Text,
  UniMessage,
  store_true,
)

from idhagnbot.plugins.daily_push.cache import DailyCache
from idhagnbot.plugins.daily_push.module import SimpleModule, register

HISTORY_API = "https://baike.baidu.com/cms/home/eventsOnHistory/{month}.json"


class HTMLStripper(HTMLParser):
  def __init__(self) -> None:
    super().__init__()
    self.f = StringIO()

  def handle_data(self, data: str) -> None:
    self.f.write(data)

  def getvalue(self) -> str:
    return self.f.getvalue()

  @staticmethod
  def strip(text: str) -> str:
    stripper = HTMLStripper()
    stripper.feed(text)
    stripper.close()
    return stripper.getvalue()


class ApiItem(TypedDict):
  year: int
  title: str


ApiResult = dict[str, dict[str, list[ApiItem]]]
ApiResultAdapter = TypeAdapter(ApiResult)


class Cache(BaseModel):
  items: list[ApiItem]


class HistoryCache(DailyCache):
  def __init__(self) -> None:
    super().__init__("history.json")

  async def do_update(self) -> None:
    today = date.today()
    month = f"{today.month:02}"
    day = f"{month}{today.day:02}"
    async with get_session().get(HISTORY_API.format(month=month)) as response:
      data = ApiResultAdapter.validate_python(await response.json(content_type="text/json"))
    items = data[month][day]
    for i in items:
      i["title"] = HTMLStripper.strip(i["title"])
    cache = Cache(items=items)
    with self.path.open("w") as f:
      f.write(cache.model_dump_json())

  def get(self) -> tuple[datetime, list[ApiItem]]:
    with self.date_path.open() as f:
      date = datetime.fromisoformat(f.read())
    with self.path.open() as f:
      cache = Cache.model_validate_json(f.read())
    return date, cache.items

  def format(self) -> str:
    date, items = self.get()
    lines = [f"今天是{date.month}月{date.day}日，历史上的今天是："]
    lines.extend(f"{i['year']} - {i['title']}" for i in items)
    return "\n".join(lines)


CACHE = HistoryCache()


@register("history")
class HistoryModule(SimpleModule):
  async def format(self) -> list[UniMessage[Segment]]:
    await CACHE.ensure()
    return [UniMessage(Text(CACHE.format()))]


history = (
  CommandBuilder()
  .node("history")
  .parser(
    Alconna(
      "历史",
      Option(
        "--no-cache",
        dest="no_cache",
        action=store_true,
        default=False,
        help_text="禁用缓存",
      ),
      meta=CommandMeta("历史上的今天"),
    ),
  )
  .build()
)


@history.handle()
async def _(*, no_cache: bool) -> None:
  if no_cache:
    await CACHE.update()
  else:
    await CACHE.ensure()
  await UniMessage(Text(CACHE.format())).send()
