from collections.abc import Callable

from arclet import letoderea
from arclet.entari.event.plugin import (
    PluginLoadedFailed,
    PluginLoadedSuccess,
    PluginUnloaded,
)
from arclet.entari.plugin.service import plugin_service
from arclet.letoderea.scope import SubscriberSlot

HookFn = Callable[[str, SubscriberSlot], None]


class Hooker:
    def __init__(self, fn: HookFn) -> None:
        self.fn = fn
        self.seen_subscribers: dict[str, set[str]] = {}

    def __call__(self, plugin_id: str, slot: SubscriberSlot) -> None:
        ids = self.seen_subscribers.setdefault(plugin_id, set())
        if slot.subscriber.id in ids:
            return
        ids.add(slot.subscriber.id)
        self.fn(plugin_id, slot)

    def unload(self, plugin_id: str) -> None:
        self.seen_subscribers.pop(plugin_id, None)


subscriber_hookers: dict[str, set[Hooker]] = {}


def hook_by_id(plugin_id: str, slot: SubscriberSlot) -> None:
    key = f"{plugin_id}:{slot.subscriber.label}"
    if key in subscriber_hookers:
        for hooker in subscriber_hookers[key]:
            hooker(plugin_id, slot)


global_hookers: set[Hooker] = {Hooker(hook_by_id)}


@letoderea.on(PluginLoadedSuccess)
async def on_loaded_success(event: PluginLoadedSuccess) -> None:
    plugin = plugin_service.plugins[event.plugin_id]
    for subscriber in plugin._scope.subscribers:
        for hooker in global_hookers:
            hooker(event.plugin_id, subscriber)


@letoderea.on(PluginLoadedFailed)
async def on_loaded_failed(event: PluginUnloaded) -> None:
    for hooker in global_hookers:
        hooker.unload(event.plugin_id)


@letoderea.on(PluginUnloaded)
async def on_unloaded(event: PluginUnloaded) -> None:
    for hooker in global_hookers:
        hooker.unload(event.plugin_id)


def hook_subscriber(plugin_id: str, label: str, fn: HookFn) -> Callable[[], None]:
    hooker = Hooker(fn)

    if plugin_id in plugin_service.plugins:
        plugin = plugin_service.plugins[plugin_id]
        for slot in plugin._scope.subscribers:
            if slot.subscriber.label == label:
                hooker(plugin_id, slot)

    key = f"{plugin_id}:{label}"
    if key in subscriber_hookers:
        subscriber_hookers[key].add(hooker)
    else:
        subscriber_hookers[key] = {hooker}

    def dispose() -> None:
        if key in subscriber_hookers:
            hookers = subscriber_hookers[key]
            hookers.discard(hooker)
            if not hookers:
                subscriber_hookers.pop(key, None)

    return dispose


def hook_subscribers(fn: HookFn) -> Callable[[], None]:
    hooker = Hooker(fn)

    for plugin in plugin_service.plugins.values():
        for subscriber in plugin._scope.subscribers:
            hooker(plugin.id, subscriber)

    global_hookers.add(hooker)
    return lambda: global_hookers.discard(hooker)
