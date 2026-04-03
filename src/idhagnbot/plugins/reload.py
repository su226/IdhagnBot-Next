import nonebot

from idhagnbot.command import CommandBuilder
from idhagnbot.config import BaseConfig
from idhagnbot.permission import SUPERUSER

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Alconna, CommandMeta

reload = (
  CommandBuilder()
  .node("reload")
  .parser(Alconna("reload", meta=CommandMeta("热重载支持的配置")))
  .default_grant_to(SUPERUSER)
  .build()
)


@reload.handle()
async def _() -> None:
  for config in BaseConfig.all:
    if config.reloadable:
      config.reload()
  await reload.finish("已重载所有配置")
