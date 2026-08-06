from collections.abc import Callable

from arclet import letoderea
from arclet.entari.event.plugin import (
    PluginLoadedFailed,
    PluginLoadedSuccess,
    PluginUnloaded,
)
from arclet.entari.plugin import get_plugin_subscribers, get_plugins
from arclet.letoderea import Subscriber

HookFn = Callable[[str, Subscriber], None]


class Hooker:
    def __init__(self, fn: HookFn) -> None:
        self.fn = fn
        self.seen_subscribers: dict[str, set[str]] = {}

    def __call__(self, plugin_id: str, subscriber: Subscriber) -> None:
        ids = self.seen_subscribers.setdefault(plugin_id, set())
        if subscriber.id in ids:
            return
        ids.add(subscriber.id)
        self.fn(plugin_id, subscriber)

    def unload(self, plugin_id: str) -> None:
        self.seen_subscribers.pop(plugin_id, None)


hookers: set[Hooker] = set()


@letoderea.on(PluginLoadedSuccess)
async def on_loaded_success(event: PluginLoadedSuccess) -> None:
    for subscriber in get_plugin_subscribers(event.plugin_id):
        for hooker in hookers:
            hooker(event.plugin_id, subscriber)


@letoderea.on(PluginLoadedFailed)
async def on_loaded_failed(event: PluginUnloaded) -> None:
    for hooker in hookers:
        hooker.unload(event.plugin_id)


@letoderea.on(PluginUnloaded)
async def on_unloaded(event: PluginUnloaded) -> None:
    for hooker in hookers:
        hooker.unload(event.plugin_id)


def hook_subscribers(fn: HookFn) -> Callable[[], None]:
    hooker = Hooker(fn)

    for plugin in get_plugins(subplugged=True):
        for subscriber in get_plugin_subscribers(plugin):
            hooker(plugin.id, subscriber)

    hookers.add(hooker)
    return lambda: hookers.discard(hooker)
