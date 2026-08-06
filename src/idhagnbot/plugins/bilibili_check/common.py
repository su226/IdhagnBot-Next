from datetime import datetime, timedelta

from arclet.entari import metadata, plugin_config
from pydantic import BaseModel, Field, HttpUrl

from idhagnbot.data import SharedCache


class Config(BaseModel):
    update_interval: timedelta = timedelta(7)
    vtbs_api: HttpUrl = HttpUrl("https://api.vtbs.moe/v1/short")


class CacheItem(BaseModel):
    last_update: datetime
    uids: set[int]


class Cache(BaseModel):
    caches: dict[str, CacheItem] = Field(default_factory=dict)


metadata("", config=Config)
CONFIG = plugin_config(Config)
CACHE = SharedCache("bilibili_check", Cache)
