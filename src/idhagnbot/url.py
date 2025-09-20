import os
import re
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote_to_bytes

import nonebot
from nonebot import logger
from pydantic import BaseModel, Field

from idhagnbot.config import SharedData
from idhagnbot.http import get_session

nonebot.require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


class Data(BaseModel):
  tlds: set[str] = Field(default_factory=set)
  last_update: datetime = datetime(1, 1, 1, tzinfo=timezone.utc)


DATA = SharedData("url", Data)
URL_RE = re.compile(
  r"(?:https?://)?(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=-]*)?",
)
driver = nonebot.get_driver()


def extract_url(text: str) -> Generator[str, None, None]:
  data = DATA()
  for match in URL_RE.finditer(text):
    if match[1].lower() in data.tlds:
      yield match[0]


def strip_url(text: str) -> str:
  def repl(match: re.Match[str]) -> str:
    if match[1].lower() in data.tlds:
      return " "
    return match[0]

  data = DATA()
  return URL_RE.sub(repl, text)


@scheduler.scheduled_job("interval", days=7)
@driver.on_startup
async def update_tlds() -> None:
  data = DATA()
  now = datetime.now(timezone.utc)
  if now - data.last_update < timedelta(7):
    return
  logger.info("正在更新 TLD 数据")
  async with get_session().get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt") as response:
    tlds = await response.text()
  data.tlds = set(tlds.lower().splitlines()[1:])
  data.last_update = now
  DATA.dump()


def path_from_url(uri: str) -> Path:
  if not uri.startswith("file:"):
    raise ValueError(f"URI does not start with 'file:': {uri!r}")
  path = uri[5:]
  if path[:3] == "///":
    path = path[2:]
  elif path[:12] == "//localhost/":
    path = path[11:]
  if path[:3] == "///" or (path[:1] == "/" and path[2:3] in ":|"):
    path = path[1:]
  if path[1:2] == "|":
    path = path[:1] + ":" + path[2:]

  path = Path(os.fsdecode(unquote_to_bytes(path)))
  if not path.is_absolute():
    raise ValueError(f"URI is not absolute: {uri!r}")
  return path
