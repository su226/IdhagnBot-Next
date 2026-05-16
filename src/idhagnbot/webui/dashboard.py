from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

from nonebot.drivers import ASGIMixin, HTTPServerSetup, Request, Response
from pydantic import BaseModel
from yarl import URL

from idhagnbot.asyncio import gather_map
from idhagnbot.webui.common import ResponseData, authenticate


class OverviewBase(BaseModel):
  name: str
  icon: str | None = None


class OverviewString(OverviewBase):
  type: Literal["string"]
  value: str


class OverviewNumber(OverviewBase):
  type: Literal["number"]
  value: int | float
  unit: str | None = None


class OverviewRatio(OverviewBase):
  type: Literal["ratio"]
  value: int | float
  max: int | float
  unit: str | None = None


OverviewItem = OverviewString | OverviewNumber | OverviewRatio
OverviewFunc = Callable[[], Awaitable[OverviewItem]]
TOverviewFunc = TypeVar("TOverviewFunc", bound=OverviewFunc)
REGISTRY = dict[str, OverviewFunc]()


def register(key: str) -> Callable[[TOverviewFunc], TOverviewFunc]:
  def register_inner(func: TOverviewFunc) -> TOverviewFunc:
    REGISTRY[key] = func
    return func

  return register_inner


class OverviewResponseData(BaseModel):
  items: dict[str, OverviewItem]


async def handle_overview(request: Request) -> Response:
  if response := authenticate(request):
    return response
  items = await gather_map({key: func() for key, func in REGISTRY.items()})
  return ResponseData.res_success(OverviewResponseData(items=items))


def setup(driver: ASGIMixin) -> None:
  driver.setup_http_server(
    HTTPServerSetup(
      URL("/idhagnbot-api/dashboard"),
      "GET",
      "IdhagnBot Dashboard Overview",
      handle_overview,
    ),
  )
