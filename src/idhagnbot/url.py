import os
import re
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, unquote_to_bytes

import nonebot
from nonebot import logger
from pydantic import AliasChoices, BaseModel, Field
from yarl import URL

from idhagnbot.config import SharedData
from idhagnbot.http import get_session

nonebot.require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


class ClearURLsRule(BaseModel):
  url_pattern: re.Pattern[str] = Field(validation_alias=AliasChoices("url_pattern", "urlPattern"))
  complete_provider: bool = Field(
    default=False,
    validation_alias=AliasChoices("complete_provider", "completeProvider"),
  )
  rules: list[re.Pattern[str]] = Field(default_factory=list)
  referral_marketing: list[re.Pattern[str]] = Field(
    default_factory=list,
    validation_alias=AliasChoices("referral_marketing", "referralMarketing"),
  )
  raw_rules: list[re.Pattern[str]] = Field(
    default_factory=list,
    validation_alias=AliasChoices("raw_rules", "rawRules"),
  )
  exceptions: list[re.Pattern[str]] = Field(default_factory=list)
  redirections: list[re.Pattern[str]] = Field(default_factory=list)
  force_redirection: bool = Field(
    default=False,
    validation_alias=AliasChoices("force_redirection", "forceRedirection"),
  )

  def match(self, url: str) -> bool:
    return bool(self.url_pattern.match(url)) and all(
      not pattern.match(url) for pattern in self.exceptions
    )

  def __call__(self, url: str) -> str:
    for pattern in self.redirections:
      if match := pattern.match(url):
        return clear_url(unquote(match[1]))
    for pattern in self.raw_rules:
      url = pattern.sub("", url)
    yarl = URL(url)
    query_params = set[str]()
    for param in yarl.query:
      for pattern in self.rules:
        if pattern.fullmatch(param):
          query_params.add(param)
    if query_params:
      yarl = yarl.without_query_params(*query_params)
      url = str(yarl)
    return url


class ClearURLsRules(BaseModel):
  providers: dict[str, ClearURLsRule]


class Data(BaseModel):
  tlds: set[str] = Field(default_factory=set)
  clearurls_rules: list[ClearURLsRule] = Field(default_factory=list)
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


def clear_url(url: str) -> str:
  data = DATA()
  for rule in data.clearurls_rules:
    if rule.match(url):
      url = rule(url)
  return url


@scheduler.scheduled_job("interval", days=7)
@driver.on_startup
async def update_tlds() -> None:
  data = DATA()
  now = datetime.now(timezone.utc)
  if now - data.last_update < timedelta(7):
    return
  logger.info("正在更新 URL 数据")
  http = get_session()
  async with http.get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt") as response:
    tlds = await response.text()
  data.tlds = set(tlds.lower().splitlines()[1:])
  async with http.get("https://rules2.clearurls.xyz/data.minify.json") as response:
    rules = ClearURLsRules.model_validate(await response.json())
  data.clearurls_rules = list(rules.providers.values())
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
