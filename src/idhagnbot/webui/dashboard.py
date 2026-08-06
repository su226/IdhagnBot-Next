from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

from fastapi import Depends, FastAPI, Response
from pydantic import BaseModel

from idhagnbot.asyncio import gather_map
from idhagnbot.webui.common import ResponseData, authorize


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


async def handle_overview() -> Response:
    items = await gather_map({key: func() for key, func in REGISTRY.items()})
    return ResponseData.res_success(OverviewResponseData(items=items))


def setup(app: FastAPI) -> None:
    app.get("/dashboard", dependencies=[Depends(authorize)])(handle_overview)
