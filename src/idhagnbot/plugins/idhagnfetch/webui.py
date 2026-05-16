import platform
import time

import nonebot
import psutil

from idhagnbot.plugins.idhagnfetch.main import BOT_START_TIME
from idhagnbot.webui.dashboard import OverviewNumber, OverviewRatio, OverviewString, register


async def get_cpu() -> OverviewRatio:
  return OverviewRatio(
    name="系统 CPU",
    type="ratio",
    value=psutil.cpu_percent(),
    max=100.0,
    unit="%",
    icon="chip",
  )


async def get_process_cpu() -> OverviewRatio:
  return OverviewRatio(
    name="进程 CPU",
    type="ratio",
    value=psutil.Process().cpu_percent(),
    max=100.0,
    unit="%",
    icon="chip",
  )


async def get_memory() -> OverviewRatio:
  return OverviewRatio(
    name="系统内存",
    type="ratio",
    value=psutil.virtual_memory().percent,
    max=100.0,
    unit="%",
    icon="chip2",
  )


async def get_process_memory() -> OverviewRatio:
  return OverviewRatio(
    name="进程内存",
    type="ratio",
    value=psutil.Process().memory_percent(),
    max=100.0,
    unit="%",
    icon="chip2",
  )


async def get_bots() -> OverviewNumber:
  return OverviewNumber(
    name="机器人数量",
    type="number",
    value=len(nonebot.get_bots()),
    icon="bot",
  )


async def get_plugins() -> OverviewNumber:
  return OverviewNumber(
    name="插件数量",
    type="number",
    value=len(nonebot.get_loaded_plugins()),
    icon="plugin",
  )


async def get_python() -> OverviewString:
  return OverviewString(
    name="Python 版本",
    type="string",
    value=platform.python_version(),
    icon="python",
  )


async def get_uptime() -> OverviewNumber:
  return OverviewNumber(
    name="运行时间",
    type="number",
    value=time.time() - BOT_START_TIME,
    unit="s",
    icon="time",
  )


def register_all() -> None:
  register("idhagnfetch:cpu")(get_cpu)
  register("idhagnfetch:process_cpu")(get_process_cpu)
  register("idhagnfetch:memory")(get_memory)
  register("idhagnfetch:process_memory")(get_process_memory)
  register("idhagnfetch:bots")(get_bots)
  register("idhagnfetch:plugins")(get_plugins)
  register("idhagnfetch:python")(get_python)
  register("idhagnfetch:uptime")(get_uptime)
