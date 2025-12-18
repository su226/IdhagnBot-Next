import pkgutil

import nonebot
from nonebot.plugin import PluginMetadata

import idhagnbot.plugins

__all__ = ["__plugin_meta__", "load_plugins"]
__plugin_meta__ = PluginMetadata(
  name="idhagnbot",
  description="加载所有 IdhagnBot 插件的快捷方式，亦可通过配置文件排除部分插件。",
  usage="""`nonebot.load_plugin("idhagnbot")`""",
  type="application",
  homepage="https://github.com/su226/IdhagnBot-Next",
  supported_adapters={"~onebot.v11", "~satori", "~telegram"},
)


def load_plugins() -> None:
  nonebot.load_all_plugins(
    module_path=(
      f"idhagnbot.plugins.{module.name}"
      for module in pkgutil.iter_modules(idhagnbot.plugins.__path__)
    ),
    plugin_dir=(),
  )


if "__plugin__" in globals():
  load_plugins()
