import re
from io import BytesIO

from anyio.to_thread import run_sync
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, PrivateAttr

from idhagnbot.asyncio import gather_seq
from idhagnbot.config import SharedConfig
from idhagnbot.http import BROWSER_UA, get_session
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


CONFIG = SharedConfig("bilibili_activity", Config, "eager")
IMAGE_GAP = 10


class IgnoredException(Exception):
  pass


def check_ignore(content: str) -> None:
  for regex in CONFIG().ignore_regexs:
    if regex.search(content):
      raise IgnoredException(regex)


async def fetch_image(url: str) -> Image.Image:
  async with get_session().get(url, headers={"User-Agent": BROWSER_UA}) as response:
    data = await response.read()
  return await run_sync(lambda: ImageOps.exif_transpose(Image.open(BytesIO(data))))


async def fetch_images(*urls: str) -> tuple[Image.Image, ...]:
  return await gather_seq(fetch_image(url) for url in urls)
