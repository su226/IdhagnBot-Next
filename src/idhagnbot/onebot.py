import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from weakref import WeakKeyDictionary

from arclet.entari import Account

__all__ = [
    "LLONEBOT",
    "NAPCAT",
    "Rkey",
    "get_implementation",
    "get_rkey",
    "get_rkey_cached",
]


@dataclass
class Rkey:
    rkey: str
    created_at: datetime
    expire_at: datetime


@dataclass
class Rkeys:
    private: Rkey
    group: Rkey


implementations: WeakKeyDictionary[Account, str] = WeakKeyDictionary()
impl_locks: WeakKeyDictionary[Account, asyncio.Lock] = WeakKeyDictionary()
rkey_cache: WeakKeyDictionary[Account, Rkeys] = WeakKeyDictionary()
rkey_locks: WeakKeyDictionary[Account, asyncio.Lock] = WeakKeyDictionary()
LLONEBOT = "LLOneBot"
NAPCAT = "NapCat.Onebot"
SNOWLUNA = "SnowLuma"


async def get_implementation(bot: Account) -> str:
    if bot not in implementations:
        lock = impl_locks.setdefault(bot, asyncio.Lock())
        async with lock:
            if bot not in implementations:
                info = await bot.internal("get_version_info")
                implementations[bot] = info["app_name"]
    return implementations[bot]


async def get_rkey(bot: Account) -> Rkeys:
    impl = await get_implementation(bot)
    if impl == LLONEBOT:
        raw = await bot.internal("get_rkey")
        created_at = datetime.fromisoformat(raw["updated_time"])
        expire_at = datetime.fromtimestamp(raw["expired_time"])
        rkeys = Rkeys(
            Rkey(
                raw["private_key"].removeprefix("&rkey="),
                created_at,
                expire_at,
            ),
            Rkey(
                raw["group_key"].removeprefix("&rkey="),
                created_at,
                expire_at,
            ),
        )
    elif impl in (NAPCAT, SNOWLUNA):
        raw = await bot.internal("get_rkey")
        private = None
        group = None
        for raw_rkey in raw:
            created_at = datetime.fromtimestamp(raw_rkey["created_at"])
            rkey = Rkey(
                raw_rkey["rkey"].removeprefix("&rkey="),
                created_at,
                created_at + timedelta(seconds=raw_rkey["ttl"]),
            )
            if raw_rkey["type"] == "private":
                private = rkey
            elif raw_rkey["type"] == "group":
                group = rkey
        if not private or not group:
            raise ValueError("未获取到 rkey")
        rkeys = Rkeys(private, group)
    else:
        raise ValueError(f"未知 OneBot 实现 {impl!r}，无法获取 rkey")
    rkey_cache[bot] = rkeys
    return rkeys


def _is_rkey_cache_valid(bot: Account) -> bool:
    if bot not in rkey_cache:
        return False
    now = datetime.now()
    rkeys = rkey_cache[bot]
    return now < rkeys.private.expire_at and now < rkeys.group.expire_at


async def get_rkey_cached(bot: Account) -> Rkeys:
    if not _is_rkey_cache_valid(bot):
        lock = rkey_locks.setdefault(bot, asyncio.Lock())
        async with lock:
            if not _is_rkey_cache_valid(bot):
                return await get_rkey(bot)
    return rkey_cache[bot]
