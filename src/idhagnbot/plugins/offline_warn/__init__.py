import time

import nonebot
from nonebot import logger
from nonebot.adapters import Bot

from idhagnbot.plugins.offline_warn.common import queue_message, send_queued_messages

nonebot.require("nonebot_plugin_apscheduler")
nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_localstore import get_data_file

try:
  import idhagnbot.plugins.offline_warn.onebot as _
except ImportError:
  pass


FILENAME = get_data_file("idhagnbot", "poweroff_warn.txt")
driver = nonebot.get_driver()
shutting_down = False


@driver.on_startup
async def _() -> None:
  if FILENAME.exists():
    with FILENAME.open() as f:
      crash_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(f.read())))
      now_str = time.strftime("%Y-%m-%d %H:%M:%S")
      prefix = f"机器人在 {crash_str} 到 {now_str} 之间可能有非正常退出"
      if driver.env == "dev":
        logger.info(prefix + "，但当前处于调试模式，将不会发送警告。")
      else:
        logger.warning(prefix + "，将发送警告！")
        await queue_message(prefix + "，请注意！")
  write_timestamp()


@scheduler.scheduled_job("interval", minutes=1)
def write_timestamp() -> None:
  with FILENAME.open("w") as f:
    f.write(str(time.time()))


@driver.on_shutdown
async def _() -> None:
  global shutting_down
  shutting_down = True
  FILENAME.unlink()


driver.on_bot_connect(send_queued_messages)


@driver.on_bot_disconnect
async def _(bot: Bot) -> None:
  if shutting_down:
    return
  now_str = time.strftime("%Y-%m-%d %H:%M:%S")
  prefix = f"后端 {bot.adapter.get_name()} {bot.self_id} 在 {now_str} 左右断开"
  logger.warning(prefix + "，将发送警告！")
  await queue_message(prefix + "，请注意！")
