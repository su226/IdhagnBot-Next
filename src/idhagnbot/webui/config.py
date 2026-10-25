import json
from typing import TYPE_CHECKING, Any

from anyio import Path
from arclet.entari.config import EntariConfig
from arclet.entari.plugin import (
    get_plugins,
    plugin_service,
)
from arclet.entari.plugin.apply import applier
from creart import it
from fastapi import APIRouter, Depends, FastAPI, Response
from launart import Launart
from pydantic import BaseModel, Field

from idhagnbot.webui.common import ResponseData, authorize

if TYPE_CHECKING:
    from arclet.entari.builtins.auto_reload import Watcher


class ConfigGetResponseData(BaseModel):
    config: str
    json_schema: dict[str, Any] = Field(alias="schema")


def get_watcher() -> Watcher | None:
    auto_reload = plugin_service.plugins.get("arclet.entari.builtins.auto_reload")
    if not auto_reload:
        return None
    return it(Launart).get_component(auto_reload.module.Watcher)


async def reload() -> None:
    watcher = get_watcher()
    if watcher and watcher.config.watch_config:
        return
    await applier.apply(EntariConfig.instance.path, source="idhagnbot_webui")


async def get_config() -> Response:
    async with await Path(EntariConfig.instance.path).open() as file:
        config = await file.read()
    EntariConfig.instance.generate_schema(get_plugins())
    schema_path = EntariConfig.instance.path.with_name("entari.schema.json")
    async with await Path(schema_path).open() as file:
        schema = json.loads(await file.read())
    return ResponseData.res_success(ConfigGetResponseData(config=config, schema=schema))


class SaveConfigRequestData(BaseModel):
    config: str


async def save_config(data: SaveConfigRequestData) -> Response:
    async with await Path(EntariConfig.instance.path).open("w") as file:
        await file.write(data.config)
    await reload()
    return ResponseData.res_success(None)


async def reload_config() -> Response:
    await reload()
    async with await Path(EntariConfig.instance.path).open() as file:
        config = await file.read()
    EntariConfig.instance.generate_schema(get_plugins())
    schema_path = EntariConfig.instance.path.with_name("entari.schema.json")
    async with await Path(schema_path).open() as file:
        schema = json.loads(await file.read())
    return ResponseData.res_success(ConfigGetResponseData(config=config, schema=schema))


def setup(app: FastAPI) -> None:
    router = APIRouter(prefix="/config", dependencies=[Depends(authorize)])
    router.get("")(get_config)
    router.post("")(save_config)
    router.post("/reload")(reload_config)
    app.include_router(router)
