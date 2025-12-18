import random
import re
from datetime import datetime, timedelta, timezone
from functools import cached_property

import nonebot
from arclet.alconna import AllParam
from nonebot import logger
from nonebot.typing import T_State
from pydantic import BaseModel, Field, HttpUrl, TypeAdapter
from typing_extensions import TypedDict

from idhagnbot.asyncio import create_background_task
from idhagnbot.command import CommandBuilder
from idhagnbot.config import SharedCache, SharedConfig
from idhagnbot.context import BotAnyNick, BotId
from idhagnbot.help import COMMAND_PREFIX
from idhagnbot.http import get_session
from idhagnbot.itertools import batched
from idhagnbot.message import UniMsg
from idhagnbot.permission import permission

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_apscheduler")
nonebot.require("nonebot_plugin_localstore")
nonebot.require("idhagnbot.plugins.error")
from nonebot_plugin_alconna import (
  Alconna,
  Args,
  CommandMeta,
  CustomNode,
  Image,
  Match,
  Reference,
  Text,
  UniMessage,
)
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_localstore import get_cache_dir

from idhagnbot.plugins.error import send_error


class Config(BaseModel):
  proxy: HttpUrl | None = None

  @property
  def proxy_aiohttp(self) -> str | None:
    return str(self.proxy) if self.proxy else None


class Cache(BaseModel):
  dates: list[str] = Field(default_factory=list)
  emojis: dict[str, str] = Field(default_factory=dict)
  combinations: dict[str, int] = Field(default_factory=dict)
  updated: datetime = datetime(1, 1, 1, tzinfo=timezone.utc)

  @cached_property
  def single_regex(self) -> re.Pattern[str]:
    emojis = "|".join(self.emojis)
    return re.compile(f"(?:{emojis})\\ufe0f?")

  @cached_property
  def double_regex(self) -> re.Pattern[str]:
    emojis = "|".join(self.emojis)
    return re.compile(f"((?:{emojis})\\ufe0f?)\\s*\\+?\\s*((?:{emojis})\\ufe0f?)")


class ApiCombination(TypedDict):
  leftEmoji: str
  rightEmoji: str
  date: str


class ApiEmoji(TypedDict):
  emoji: str
  combinations: dict[str, list[ApiCombination]]


class ApiResponse(TypedDict):
  data: dict[str, ApiEmoji]


ApiResponseAdapter = TypeAdapter(ApiResponse)
API = "https://raw.githubusercontent.com/xsalazar/emoji-kitchen-backend/main/app/metadata.json"
URL_PREFIX = "https://www.gstatic.com/android/keyboard/emojikitchen"
CONFIG = SharedConfig("emojimix", Config)
CACHE = SharedCache("emojimix", Cache)
CACHE_DIR = get_cache_dir("idhagnbot") / "emojimix"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def clear_emoji(emoji: str) -> str:
  return emoji.removesuffix("\ufe0f")


@scheduler.scheduled_job("interval", days=7)
async def update_cache() -> None:
  try:
    logger.info("正在更新 emojimix 数据")
    async with get_session().get(API, proxy=CONFIG().proxy_aiohttp) as response:
      data = ApiResponseAdapter.validate_json(await response.text())
    dates = list[str]()
    dates_map = dict[str, int]()
    emojis = dict[str, str]()
    combinations = dict[str, int]()
    for emoji in data["data"].values():
      emojis[clear_emoji(emoji["emoji"])] = emoji["emoji"]
      for comb in emoji["combinations"].values():
        combination = comb[0]
        emoji1 = combination["leftEmoji"]
        emoji2 = combination["rightEmoji"]
        date = combination["date"]
        if date not in dates_map:
          dates_map[date] = len(dates)
          dates.append(date)
        combinations[emoji1 + "|" + emoji2] = dates_map[date]
    cache = CACHE()
    cache.dates = dates
    cache.emojis = emojis
    cache.combinations = combinations
    cache.updated = datetime.now(timezone.utc)
    CACHE.dump()
    logger.success("更新 emojimix 数据成功")
  except Exception as e:
    description = "更新 emojimix 数据失败"
    logger.exception(description)
    create_background_task(send_error("emojimix", description, e))


@nonebot.get_driver().on_startup
async def _() -> None:
  cache = CACHE()
  now = datetime.now(timezone.utc)
  if now - cache.updated > timedelta(7):
    create_background_task(update_cache())


def get_code(emoji: str) -> str:
  return "-".join(f"u{ord(char):x}" for char in emoji)


async def handle_emojimix_common(emoji1: str, emoji2: str, swap: bool, show: bool) -> None:
  code1 = get_code(emoji1)
  code2 = get_code(emoji2)
  cache = CACHE()
  if swap:
    date = cache.dates[cache.combinations[emoji2 + "|" + emoji1]]
    filename = f"{code2}_{code1}.png"
    url = f"{URL_PREFIX}/{date}/{code2}/{filename}"
  else:
    date = cache.dates[cache.combinations[emoji1 + "|" + emoji2]]
    filename = f"{code1}_{code2}.png"
    url = f"{URL_PREFIX}/{date}/{code1}/{filename}"
  path = CACHE_DIR / filename
  if not path.exists():
    async with get_session().get(url, proxy=CONFIG().proxy_aiohttp) as response:
      with path.open("wb") as f:
        f.write(await response.read())
  message = UniMessage(Image(path=path, sticker=True))
  if show:
    message = Text(f"{emoji1}+{emoji2}=") + message
  await message.send()


emojimix_command = (
  CommandBuilder()
  .node("emojimix.command")
  .parser(
    Alconna(
      "emojimix",
      Args["emojis?", AllParam(str)],
      meta=CommandMeta(
        "融合两个 Emoji",
        usage=f"""\
{COMMAND_PREFIX}emojimix list - 列出支持的 emoji
{COMMAND_PREFIX}emojimix <emoji> list - 列出可以和这个 emoji 融合的其他 emoji
{COMMAND_PREFIX}emojimix - 随机融合
{COMMAND_PREFIX}emojimix <emoji> - 半随机融合
{COMMAND_PREFIX}emojimix <emoji1>+<emoji2> - 融合两个 emoji（加号可以省略）
亦可直接发送 <emoji1>+<emoji2> 触发（加号可以省略）""",
        example=f"""\
{COMMAND_PREFIX}emojimix list
{COMMAND_PREFIX}emojimix 🪄 list
{COMMAND_PREFIX}emojimix
{COMMAND_PREFIX}emojimix 🪄
{COMMAND_PREFIX}emojimix 🪄+😀""",
        author="""\
数据来自 https://github.com/xsalazar/emoji-kitchen
图片来自 Google""",
      ),
    ),
  )
  .build()
)


@emojimix_command.handle()
async def _(*, emojis: Match[UniMessage[Text]], bot_id: BotId, bot_nick: BotAnyNick) -> None:
  cache = CACHE()

  if not emojis.available:
    choices = list(cache.combinations)
    emoji1, emoji2 = random.choice(choices).split("|")
    await handle_emojimix_common(emoji1, emoji2, swap=False, show=True)
    return

  text = emojis.result.extract_plain_text()

  if (starts := text.startswith("list")) or text.endswith("list"):
    emoji1 = text[4:].lstrip() if starts else text[:-4].rstrip()
    if not emoji1:
      nodes = [
        CustomNode(bot_id, bot_nick, UniMessage(Text("支持的 emoji（并不是所有组合都存在）："))),
      ]
      nodes.extend(
        CustomNode(bot_id, bot_nick, " | ".join(chunk))
        for chunk in batched(cache.emojis.values(), 50)
      )
      await UniMessage(Reference(nodes=nodes)).send()
      return

    if cache.single_regex.fullmatch(emoji1):
      emoji1 = cache.emojis[clear_emoji(emoji1)]
      available = []
      for pair in cache.combinations:
        if pair.endswith(emoji1):
          available.append(pair[: -len(emoji1) - 1])
        elif pair.startswith(emoji1):
          available.append(pair[len(emoji1) + 1 :])
      nodes = [
        CustomNode(bot_id, bot_nick, UniMessage(Text(f"可以和 {emoji1} 组合的 emoji："))),
      ]
      nodes.extend(
        CustomNode(bot_id, bot_nick, " | ".join(chunk)) for chunk in batched(available, 50)
      )
      await UniMessage(Reference(nodes=nodes)).send()
      return

    await UniMessage(Text("用法错误或不支持当前 Emoji")).send()
    return

  if match := cache.single_regex.fullmatch(text):
    emoji1 = cache.emojis[clear_emoji(match[0])]
    choices = list(cache.emojis.values())
    while True:
      emoji2 = random.choice(choices)
      if emoji1 + "|" + emoji2 in cache.combinations:
        swap = False
        break
      if emoji2 + "|" + emoji1 in cache.combinations:
        swap = True
        break
    await handle_emojimix_common(emoji1, emoji2, swap, show=True)
    return

  if match := cache.double_regex.fullmatch(emojis.result.extract_plain_text()):
    emoji1 = cache.emojis[clear_emoji(match[1])]
    emoji2 = cache.emojis[clear_emoji(match[2])]
    if emoji1 + "|" + emoji2 in cache.combinations:
      swap = False
    elif emoji2 + "|" + emoji1 in cache.combinations:
      swap = True
    else:
      await UniMessage(Text("组合不存在")).send()
      return
    await handle_emojimix_common(emoji1, emoji2, swap, show=False)
    return

  await UniMessage(Text("用法错误或不支持当前 Emoji")).send()


async def check_emojimix_quick(message: UniMsg, state: T_State) -> bool:
  if not all(isinstance(segment, Text) for segment in message):
    return False
  cache = CACHE()
  if match := cache.double_regex.fullmatch(message.extract_plain_text().strip()):
    emoji1 = cache.emojis[clear_emoji(match[1])]
    emoji2 = cache.emojis[clear_emoji(match[2])]
    if emoji1 + "|" + emoji2 in cache.combinations:
      state["emoji1"] = emoji1
      state["emoji2"] = emoji2
      state["swap"] = False
      return True
    if emoji2 + "|" + emoji1 in cache.combinations:
      state["emoji1"] = emoji1
      state["emoji2"] = emoji2
      state["swap"] = True
      return True
  return False


emojimix_quick = nonebot.on_message(check_emojimix_quick, permission=permission("emojimix.quick"))


@emojimix_quick.handle()
async def _(*, state: T_State) -> None:
  emoji1 = state["emoji1"]
  emoji2 = state["emoji2"]
  swap = state["swap"]
  await handle_emojimix_common(emoji1, emoji2, swap, show=False)
