from collections.abc import Callable
from typing import Any

from arclet.entari import ConfigReload
from arclet.entari.plugin import get_plugin
from arclet.entari.plugin.service import plugin_service
from arclet.letoderea import on
from pydantic import BaseModel

type HandlerFn = Callable[[Any, Any], None]
HANDLERS: dict[str, HandlerFn] = {}
ROOT_PLUGIN_ID = "idhagnbot"
ROOT_PLUGIN = plugin_service.plugins[ROOT_PLUGIN_ID]


@on(ConfigReload)
async def handle_config_reload(event: ConfigReload) -> bool:
    if event.scope != "plugin" or event.key != ROOT_PLUGIN_ID:
        return False
    differences: list[tuple[HandlerFn, Any, Any]] = []
    for plugin_id in ROOT_PLUGIN.subplugins:
        plugin = plugin_service.plugins[plugin_id]
        if not plugin.metadata or not plugin.metadata.config:
            continue
        key = plugin_id.removeprefix(ROOT_PLUGIN_ID)
        old_value = event.old.get(key, {})
        new_value = event.value.get(key, {})
        if old_value == new_value:
            continue
        if key not in HANDLERS:
            return False
        differences.append((HANDLERS[key], old_value, new_value))
    for handler, old_value, new_value in differences:
        handler(old_value, new_value)
    return True


class ConfigWrapper[T: BaseModel]:
    model_type: type[T]
    current: T
    reload_handler: Callable[[T, T], None] | None

    def __init__(self, model_type: type[T]) -> None:
        plugin = get_plugin(1)
        key = plugin.id.removeprefix(ROOT_PLUGIN_ID)
        HANDLERS[key] = self.__apply_new_config
        self.model_type = model_type
        self.current = model_type.model_validate(plugin.config)
        self.reload_handler = None

    def on_reload(self, fn: Callable[[T, T], None]) -> Callable[[T, T], None]:
        self.reload_handler = fn
        return fn

    def __apply_new_config(self, old: Any, new: Any) -> None:
        old_model = self.current
        new_model = self.model_type.model_validate(new)
        self.current = new_model
        if self.reload_handler:
            self.reload_handler(old_model, new_model)
