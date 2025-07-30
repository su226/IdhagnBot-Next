import asyncio
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image, ImageOps
from pydantic import BaseModel, Field, PrivateAttr

from idhagnbot.config import SharedConfig, SharedData
from idhagnbot.http import get_session
from idhagnbot.target import TargetConfig


class User(BaseModel):
  uid: int
  targets: list[TargetConfig]
  _name: str = PrivateAttr("未知用户")
  _offset: int = PrivateAttr(-1)


class Config(BaseModel):
  interval: int = 10
  concurrency: int = 1
  users: list[User] = Field(default_factory=list)
  ignore_regexs: list[re.Pattern[str]] = Field(default_factory=list)
  ignore_forward_regexs: list[re.Pattern[str]] = Field(default_factory=list)
  ignore_forward_lottery: bool = False
  warn_interval: timedelta = timedelta(1)
  warn_target: list[TargetConfig] = Field(default_factory=list)


class Data(BaseModel):
  last_warn: datetime = datetime(1, 1, 1, tzinfo=timezone.utc)


CONFIG = SharedConfig("bilibili_activity", Config, "eager")
DATA = SharedData("bilibili_activity", Data)
IMAGE_GAP = 10


class IgnoredException(Exception):
  pass


def check_ignore(content: str) -> None:
  for regex in CONFIG().ignore_regexs:
    if regex.search(content):
      raise IgnoredException(regex)


async def fetch_image(url: str) -> Image.Image:
  async with get_session().get(url) as response:
    data = await response.read()
  return await asyncio.to_thread(lambda: ImageOps.exif_transpose(Image.open(BytesIO(data))))


async def fetch_images(*urls: str) -> list[Image.Image]:
  return await asyncio.gather(*(fetch_image(url) for url in urls))
