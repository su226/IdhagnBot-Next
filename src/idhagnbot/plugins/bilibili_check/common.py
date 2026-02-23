from datetime import datetime, timedelta

from pydantic import BaseModel, Field, HttpUrl

from idhagnbot.config import SharedCache, SharedConfig


class Config(BaseModel):
  update_interval: timedelta = timedelta(7)
  vtbs_api: HttpUrl = HttpUrl("https://api.vtbs.moe/v1/short")


class CacheItem(BaseModel):
  last_update: datetime
  uids: set[int]


class Cache(BaseModel):
  caches: dict[str, CacheItem] = Field(default_factory=dict)


CONFIG = SharedConfig("bilibili_check", Config)
CACHE = SharedCache("bilibili_check", Cache)
