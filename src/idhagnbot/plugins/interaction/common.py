from collections.abc import Awaitable, Callable

import nonebot
from nonebot.adapters import Bot, Event

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Reply

REPLY_EXTRACT_REGISTRY = dict[str, Callable[[Bot, Event, Reply], Awaitable[str]]]()
