import re
from datetime import timedelta

from arclet.entari import metadata, plugin_config
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, PrivateAttr

from idhagnbot.asyncio import gather_seq
from idhagnbot.http import BROWSER_UA
from idhagnbot.image import open_url


class User(BaseModel):
    uid: int
    targets: list[str]
    _name: str = PrivateAttr(default="未知用户")
    _offset: int = PrivateAttr(default=-1)


class Config(BaseModel):
    interval: timedelta = timedelta(seconds=10)
    concurrency: int = 1
    users: list[User] = Field(default_factory=list)
    ignore_regexs: list[re.Pattern[str]] = Field(default_factory=list)
    ignore_forward_regexs: list[re.Pattern[str]] = Field(default_factory=list)
    ignore_forward_lottery: bool = False


metadata("", config=Config)
CONFIG = plugin_config(Config)
IMAGE_GAP = 10


class IgnoredException(Exception):
    pass


def check_ignore(content: str) -> None:
    for regex in CONFIG.ignore_regexs:
        if regex.search(content):
            raise IgnoredException(regex)


async def fetch_image(url: str) -> Image.Image:
    return await open_url(url, ImageOps.exif_transpose, {"User-Agent": BROWSER_UA})


async def fetch_images(*urls: str) -> list[Image.Image]:
    return await gather_seq(fetch_image(url) for url in urls)
