import re
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

from arclet.entari import Ready
from arclet.entari.scheduler import schedule, timer
from arclet.letoderea import on
from loguru import logger
from pydantic import AliasChoices, BaseModel, Field
from yarl import URL

from idhagnbot.asyncio import create_background_task
from idhagnbot.data import SharedCache
from idhagnbot.http import get_session
from idhagnbot.plugins.error_report import send_error


class ClearURLsRule(BaseModel):
    url_pattern: re.Pattern[str] = Field(
        validation_alias=AliasChoices("url_pattern", "urlPattern"),
    )
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


class Cache(BaseModel):
    tlds: set[str] = Field(default_factory=set)
    clearurls_rules: list[ClearURLsRule] = Field(default_factory=list)
    last_update: datetime = datetime(1, 1, 1, tzinfo=UTC)


CACHE = SharedCache("url", Cache)
URL_RE = re.compile(
    r"(?:https?://)?(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=-]*)?",
)


def extract_url(text: str) -> Generator[str]:
    data = CACHE()
    for match in URL_RE.finditer(text):
        if match[1].lower() in data.tlds:
            yield match[0]


def strip_url(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        if match[1].lower() in data.tlds:
            return " "
        return match[0]

    data = CACHE()
    return URL_RE.sub(repl, text)


def clear_url(url: str) -> str:
    data = CACHE()
    for rule in data.clearurls_rules:
        if rule.match(url):
            url = rule(url)
    return url


async def update_tlds() -> None:
    try:
        cache = CACHE()
        logger.info("正在更新 URL 数据")
        http = get_session()
        async with http.get(
            "https://data.iana.org/TLD/tlds-alpha-by-domain.txt",
        ) as response:
            tlds = await response.text()
        cache.tlds = set(tlds.lower().splitlines()[1:])
        async with http.get(
            "https://rules2.clearurls.xyz/data.minify.json",
        ) as response:
            rules = ClearURLsRules.model_validate(await response.json())
        cache.clearurls_rules = list(rules.providers.values())
        cache.last_update = datetime.now(UTC)
        CACHE.dump()
        logger.success("更新 URL 数据成功")
    except Exception as e:
        description = "更新 URL 数据失败"
        logger.exception(description)
        create_background_task(send_error("url", description, e))


schedule(timer.every_week())(update_tlds)


@on(Ready)
async def on_ready() -> None:
    cache = CACHE()
    now = datetime.now(UTC)
    if now - cache.last_update > timedelta(7):
        create_background_task(update_tlds())
