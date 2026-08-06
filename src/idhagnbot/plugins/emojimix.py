import random
import re
from datetime import UTC, datetime, timedelta
from functools import cached_property
from itertools import batched
from typing import TypedDict

from arclet import letoderea
from arclet.alconna import Alconna, AllParam, Args, CommandMeta
from arclet.entari import (
    Image,
    Message,
    MessageChain,
    MessageCreatedEvent,
    Ready,
    Session,
    Text,
    command,
    enter_if,
    local_data,
    metadata,
    plugin_config,
)
from arclet.entari.command import Match
from arclet.entari.scheduler import schedule, timer
from arclet.letoderea import BLOCK, Contexts, ExitState
from entari_plugin_permission import require_permission  # entari: plugin
from loguru import logger
from pydantic import BaseModel, Field, HttpUrl, TypeAdapter

from idhagnbot.asyncio import create_background_task
from idhagnbot.data import SharedCache
from idhagnbot.http import get_session
from idhagnbot.plugins.error_report import send_error
from idhagnbot.plugins.record import recorded_non_command


class Config(BaseModel):
    proxy: HttpUrl | None = None

    @property
    def proxy_aiohttp(self) -> str | None:
        return str(self.proxy) if self.proxy else None


class Cache(BaseModel):
    dates: list[str] = Field(default_factory=list)
    emojis: dict[str, str] = Field(default_factory=dict)
    combinations: dict[str, int] = Field(default_factory=dict)
    updated: datetime = datetime(1, 1, 1, tzinfo=UTC)

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
metadata("", config=Config)
CONFIG = plugin_config(Config)
CACHE = SharedCache("emojimix", Cache)
CACHE_DIR = local_data.get_cache_dir("idhagnbot") / "emojimix"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def clear_emoji(emoji: str) -> str:
    return emoji.removesuffix("\ufe0f")


async def update_cache() -> None:
    try:
        logger.info("正在更新 emojimix 数据")
        async with get_session().get(API, proxy=CONFIG.proxy_aiohttp) as response:
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
        cache.updated = datetime.now(UTC)
        CACHE.dump()
        logger.success("更新 emojimix 数据成功")
    except Exception as e:
        description = "更新 emojimix 数据失败"
        logger.exception(description)
        create_background_task(send_error("emojimix", description, e))


schedule(timer.every_week(), label="idhagnbot-emojimix-update")(update_cache)


@letoderea.on(Ready)
async def on_ready() -> None:
    cache = CACHE()
    now = datetime.now(UTC)
    if now - cache.updated > timedelta(7):
        create_background_task(update_cache())


def get_code(emoji: str) -> str:
    return "-".join(f"u{ord(char):x}" for char in emoji)


async def handle_emojimix_common(
    session: Session,
    emoji1: str,
    emoji2: str,
    swap: bool,
    show: bool,
) -> None:
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
        async with get_session().get(url, proxy=CONFIG.proxy_aiohttp) as response:
            with path.open("wb") as f:
                f.write(await response.read())
    message = MessageChain(Image.of(path=path))
    if show:
        message = Text(f"{emoji1}+{emoji2}=") + message
    await session.send(message)


@command.on(
    Alconna(
        "emojimix",
        Args["emojis?", AllParam(str)],
        meta=CommandMeta(
            "融合两个 Emoji",
            usage="""\
emojimix list - 列出支持的 emoji
emojimix <emoji> list - 列出可以和这个 emoji 融合的其他 emoji
emojimix - 随机融合
emojimix <emoji> - 半随机融合
emojimix <emoji1>+<emoji2> - 融合两个 emoji（加号可以省略）
亦可直接发送 <emoji1>+<emoji2> 触发（加号可以省略）""",
            example="""\
emojimix list
emojimix 🪄 list
emojimix
emojimix 🪄
emojimix 🪄+😀""",
            author="""\
数据来自 https://github.com/xsalazar/emoji-kitchen
图片来自 Google""",
        ),
    ),
)
@letoderea.propagate(require_permission("idhagnbot.emojimix.command", prompt=True))
async def handle_emojimix_command(
    emojis: Match[MessageChain[Text]],
    session: Session,
) -> None:
    cache = CACHE()

    if not emojis.available:
        choices = list(cache.combinations)
        emoji1, emoji2 = random.choice(choices).split("|")
        await handle_emojimix_common(session, emoji1, emoji2, swap=False, show=True)
        return

    text = emojis.result.extract_plain_text()

    if (starts := text.startswith("list")) or text.endswith("list"):
        emoji1 = text[4:].lstrip() if starts else text[:-4].rstrip()
        if not emoji1:
            nodes = [
                Message(content=[Text("支持的 emoji（并不是所有组合都存在）：")]),
            ]
            nodes.extend(
                Message(content=[Text(" | ".join(chunk))])
                for chunk in batched(cache.emojis.values(), 50, strict=False)
            )
            await session.send([Message(forward=True, content=nodes)])
            return

        if cache.single_regex.fullmatch(emoji1):
            emoji1 = cache.emojis[clear_emoji(emoji1)]
            available = list[str]()
            for pair in cache.combinations:
                if pair.endswith(emoji1):
                    available.append(pair[: -len(emoji1) - 1])
                elif pair.startswith(emoji1):
                    available.append(pair[len(emoji1) + 1 :])
            nodes = [
                Message(content=[Text(f"可以和 {emoji1} 组合的 emoji：")]),
            ]
            nodes.extend(
                Message(content=[Text(" | ".join(chunk))])
                for chunk in batched(available, 50, strict=False)
            )
            await session.send([Message(forward=True, content=nodes)])
            return

        await session.send([Text("用法错误或不支持当前 Emoji")])
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
        await handle_emojimix_common(session, emoji1, emoji2, swap, show=True)
        return

    if match := cache.double_regex.fullmatch(emojis.result.extract_plain_text()):
        emoji1 = cache.emojis[clear_emoji(match[1])]
        emoji2 = cache.emojis[clear_emoji(match[2])]
        if emoji1 + "|" + emoji2 in cache.combinations:
            swap = False
        elif emoji2 + "|" + emoji1 in cache.combinations:
            swap = True
        else:
            await session.send([Text("组合不存在")])
            return
        await handle_emojimix_common(session, emoji1, emoji2, swap, show=False)
        return

    await session.send([Text("用法错误或不支持当前 Emoji")])


async def check_emojimix_quick(message: MessageChain, ctx: Contexts) -> bool:
    if not all(isinstance(segment, Text) for segment in message):
        return False
    cache = CACHE()
    if match := cache.double_regex.fullmatch(message.extract_plain_text().strip()):
        emoji1 = cache.emojis[clear_emoji(match[1])]
        emoji2 = cache.emojis[clear_emoji(match[2])]
        if emoji1 + "|" + emoji2 in cache.combinations:
            ctx["emoji1"] = emoji1
            ctx["emoji2"] = emoji2
            ctx["swap"] = False
            return True
        if emoji2 + "|" + emoji1 in cache.combinations:
            ctx["emoji1"] = emoji1
            ctx["emoji2"] = emoji2
            ctx["swap"] = True
            return True
    return False


@letoderea.on(MessageCreatedEvent)
@recorded_non_command()
@letoderea.propagate(require_permission("idhagnbot.emojimix.quick"))
@enter_if(check_emojimix_quick)
async def handle_emojimix_quick(session: Session, ctx: Contexts) -> ExitState:
    emoji1 = ctx["emoji1"]
    emoji2 = ctx["emoji2"]
    swap = ctx["swap"]
    await handle_emojimix_common(session, emoji1, emoji2, swap, show=False)
    return BLOCK
