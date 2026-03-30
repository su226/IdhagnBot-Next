from importlib.util import find_spec

from nonebot import logger

if find_spec("psutil") is None:
  logger.warning(
    "未安装 psutil，无法使用 /idhagnfetch。如需安装，请将 idhagnbot[psutil] 添加到依赖中。",
  )
else:
  import idhagnbot.plugins.idhagnfetch.main as _
