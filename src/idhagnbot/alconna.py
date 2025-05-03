import nonebot
from arclet.alconna.config import config

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Namespace

NAMESPACE = Namespace("idhagnbot", list(nonebot.get_driver().config.command_start))
config.namespaces[NAMESPACE.name] = NAMESPACE
