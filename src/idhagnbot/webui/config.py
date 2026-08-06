import asyncio
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from anyio import Path
from arclet.entari.config import EntariConfig, config_model_schema
from arclet.entari.config.model import BasicConfig
from arclet.entari.event.config import ConfigReload
from arclet.entari.plugin import (
    Plugin,
    find_plugin,
    get_plugins,
    load_plugin,
    plugin_service,
    unload_plugin_async,
)
from arclet.letoderea import post, publish
from creart import it
from fastapi import APIRouter, Depends, FastAPI, Response
from launart import Launart
from loguru import logger
from pydantic import BaseModel

from idhagnbot.webui.common import ResponseData, authorize

if TYPE_CHECKING:
    from arclet.entari.builtins.auto_reload import Watcher


class ConfigGetResponseData(BaseModel):
    config: str
    schema: dict[str, Any]


def generate_plugin_schema(plugin: Plugin, ref_root: str) -> dict[str, Any]:
    properties = {
        "$disable": {
            "type": "string",
            "description": "Expression for whether disable this plugin",
        },
        "$priority": {
            "type": "integer",
            "description": "Plugin loading priority, lower value means higher priority (default: 16)",
        },
        "$filter": {
            "type": "string",
            "description": "Plugin filter expression, which will be evaluated in the context of the plugin",
        },
    }
    for subplugin_id in plugin.subplugins:
        key = subplugin_id.removeprefix(plugin.id)
        properties[key] = generate_plugin_schema(
            plugin_service.plugins[subplugin_id],
            f"{ref_root}properties/{key}/",
        )
    if plugin.metadata is None:
        return {
            "type": "object",
            "description": "No configuration required",
            "additionalProperties": True,
            "properties": properties,
        }
    if plugin.metadata.config:
        schema = config_model_schema(plugin.metadata.config, ref_root)
        schema["properties"].update(properties)
        return schema
    return {
        "type": "object",
        "description": f"{plugin.metadata.description or plugin.metadata.name}; no configuration required",
        "additionalProperties": True,
        "properties": properties,
    }


def generate_schema_with_subplugins() -> dict[str, Any]:
    plugin_schemas = {}
    for plugin in get_plugins():
        plugin_schemas[plugin._config_key] = generate_plugin_schema(
            plugin,
            f"/properties/plugins/properties/{plugin._config_key}/",
        )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "basic": config_model_schema(BasicConfig, ref_root="/properties/basic/"),
            "plugins": {
                "type": "object",
                "description": "Plugin configurations",
                "properties": {
                    "$prefix": {
                        "description": "List of prefix config",
                        "items": {
                            "properties": {
                                "key": {
                                    "description": "Prefix key",
                                    "title": "Key",
                                    "type": "string",
                                },
                                "plugins": {
                                    "anyOf": [
                                        {"type": "string"},
                                        {
                                            "items": {
                                                "type": "string",
                                                "description": "Plugin name",
                                            },
                                            "type": "array",
                                            "uniqueItems": True,
                                        },
                                    ],
                                    "description": "List of plugins under the prefix, or select an item of $files to apply plugins",
                                    "title": "Plugins",
                                },
                            },
                            "required": ["key"],
                            "title": "Prefix Config",
                            "type": "object",
                        },
                        "type": "array",
                    },
                    "$prelude": {
                        "type": "array",
                        "items": {"type": "string", "description": "Plugin name"},
                        "description": "List of prelude plugins to load",
                        "default": [],
                        "uniqueItems": True,
                    },
                    "$files": {
                        "type": "array",
                        "items": {"type": "string", "description": "File path"},
                        "description": "List of configuration files to load",
                        "default": [],
                        "uniqueItems": True,
                    },
                    **plugin_schemas,
                },
            },
            "adapters": {
                "type": "array",
                "description": "Adapter configurations",
                "items": {
                    "type": "object",
                    "description": "Adapter configuration",
                    "properties": {
                        "$path": {
                            "type": "string",
                            "description": "Adapter Module Path",
                        },
                    },
                    "required": ["$path"],
                    "additionalProperties": True,
                },
            },
        },
        "additionalProperties": False,
        "required": ["basic"],
    }


def get_watcher() -> Watcher | None:
    auto_reload = plugin_service.plugins.get("arclet.entari.builtins.auto_reload")
    if not auto_reload:
        return None
    return it(Launart).get_component(auto_reload.module.Watcher)


async def reload() -> None:
    watcher = get_watcher()
    if watcher and watcher.config.watch_config:
        return
    old_basic = asdict(EntariConfig.instance.basic)
    old_plugin = EntariConfig.instance.plugin.copy()
    if not EntariConfig.instance.reload():
        return
    logger.info(f"Detected change in {EntariConfig.path.name!r}, reloading config...")
    new_basic = asdict(EntariConfig.instance.basic)
    for key in old_basic:
        if key in new_basic and old_basic[key] != new_basic[key]:
            logger.debug(
                f"Basic config <y>{key!r}</y> changed from <r>{old_basic[key]!r}</r> "
                f"to <g>{new_basic[key]!r}</g>",
            )
            await publish(ConfigReload("basic", key, new_basic[key], old_basic[key]))
    for key in set(new_basic) - set(old_basic):
        logger.debug(f"Basic config <y>{key!r}</y> appended")
        await publish(ConfigReload("basic", key, new_basic[key]))
    for plugin_name in old_plugin:
        if plugin_name.startswith("$"):
            continue
        pid = plugin_name.replace("::", "arclet.entari.builtins.")
        if plugin_name not in EntariConfig.instance.plugin:
            if plg := find_plugin(pid):
                if plg.is_static:
                    logger.info(f"Plugin <y>{plg.id!r}</y> is static, ignored.")
                else:
                    del plg
                    await unload_plugin_async(pid)
                    logger.info(f"Disposed plugin <blue>{pid!r}</blue>")
            continue
        old_conf = EntariConfig._clean(old_plugin[plugin_name])
        new_conf = EntariConfig.instance.plugin[plugin_name]
        if old_conf == new_conf:
            continue
        plg = find_plugin(pid)
        if not plg:
            logger.info(f"Detected <blue>{pid!r}</blue> appended, loading...")
            load_plugin(plugin_name, new_conf)
            continue
        added = set(new_conf) - set(old_conf)
        removed = set(old_conf) - set(new_conf)
        changed = {
            k for k in set(new_conf) & set(old_conf) if new_conf[k] != old_conf[k]
        }
        changes = added | removed | changed
        if "$disable" in changes:
            plg.check_disable()
            changes.remove("$disable")
        if "$dry" in changes:
            changes.remove("$dry")
            if new_conf.get("$dry", False):
                logger.debug(f"Plugin <y>{plg.id!r}</y> is dry, ignored.")
                continue
        if not changes:
            continue
        logger.debug(
            f"Plugin <y>{plugin_name!r}</y> config changed from <r>{old_conf!r}</r> "
            f"to <g>{new_conf!r}</g>",
        )
        res = await post(ConfigReload("plugin", plugin_name, new_conf, old_conf))
        if res and res.value:
            logger.debug(f"Plugin <y>{pid!r}</y> config change handled by itself.")
            continue
        if plg.is_static:
            logger.info(f"Plugin <y>{plg.id!r}</y> is static, ignored.")
            continue
        logger.info(f"Detected config of <blue>{pid!r}</blue> changed, reloading...")
        plugin_file = str(plg.module.__file__)
        _conf = plg.config.copy()

        async def load_one(
            pid: str = pid,
            plugin_name: str = plugin_name,
            new_conf: dict[str, Any] = new_conf,
            plugin_file: str = plugin_file,
            _conf: dict[str, Any] = _conf,
        ) -> None:
            await unload_plugin_async(pid)
            if plg := load_plugin(plugin_name, new_conf):
                logger.info(f"Reloaded <blue>{plg.id!r}</blue>")
                del plg
            else:
                logger.error(f"Failed to reload <blue>{plugin_name!r}</blue>")
                if watcher:
                    watcher.fail[plugin_file] = (pid, _conf)

        await asyncio.shield(load_one())
    if new := (set(EntariConfig.instance.plugin) - set(old_plugin)):
        for plugin_name in new:
            if plugin_name.startswith(("$", "~")):
                continue
            if not (plg := load_plugin(plugin_name)):
                continue
            del plg


async def get_config() -> Response:
    async with await Path(EntariConfig.instance.path).open() as file:
        config = await file.read()
    schema = generate_schema_with_subplugins()
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
    schema = generate_schema_with_subplugins()
    return ResponseData.res_success(ConfigGetResponseData(config=config, schema=schema))


def setup(app: FastAPI) -> None:
    router = APIRouter(prefix="/config", dependencies=[Depends(authorize)])
    router.get("")(get_config)
    router.post("")(save_config)
    router.post("/reload")(reload_config)
    app.include_router(router)
