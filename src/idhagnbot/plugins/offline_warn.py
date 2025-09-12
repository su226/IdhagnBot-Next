import asyncio
import time
from dataclasses import dataclass

import nonebot
from nonebot import logger
from nonebot.adapters import Bot
from nonebot.exception import ActionFailed
from pydantic import BaseModel

from idhagnbot.config import SharedConfig
from idhagnbot.target import TargetConfig

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_apscheduler")
nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_alconna import SerializeFailed, Target, UniMessage
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_localstore import get_data_file


class Config(BaseModel):
  targets: list[TargetConfig]


@dataclass
class QueuedMessage:
  message: str
  targets: list[TargetConfig]


FILENAME = get_data_file("idhagnbot", "poweroff_warn.txt")
CONFIG = SharedConfig("offline_warn", Config)
driver = nonebot.get_driver()
queued_messages = list[QueuedMessage]()
lock = asyncio.Lock()  # 防止多个机器人同时上线时出错（尤其是启动时）
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


async def select_bot(target: Target) -> Bot:
  if target.self_id:
    try:
      return nonebot.get_bot(target.self_id)
    except Exception as e:
      raise SerializeFailed("当前机器人不在线") from e
  try:
    return await target.select()
  except Exception as e:
    raise SerializeFailed("选择机器人失败") from e


async def queue_message(message: str) -> None:
  config = CONFIG()
  queued_messages.append(QueuedMessage(message, config.targets.copy()))
  await send_queued_messages()


@driver.on_bot_connect
async def send_queued_messages() -> None:
  async with lock:
    hit_messages = list[QueuedMessage]()
    for message in queued_messages:
      hit_targets = list[TargetConfig]()
      for target in message.targets:
        try:
          bot = await select_bot(target.target)
        except SerializeFailed:
          continue
        hit_targets.append(target)
        try:
          await UniMessage(message.message).send(target.target, bot)
        except ActionFailed:
          logger.exception(f"消息发送失败：{message.message}")
      for target in hit_targets:
        message.targets.remove(target)
      if not message.targets:
        hit_messages.append(message)
    for message in hit_messages:
      queued_messages.remove(message)


@driver.on_bot_disconnect
async def _(bot: Bot) -> None:
  if shutting_down:
    return
  now_str = time.strftime("%Y-%m-%d %H:%M:%S")
  prefix = f"后端 {bot.adapter.get_name()} {bot.self_id} 在 {now_str} 左右断开"
  logger.warning(prefix + "，将向超管发送警告！")
  await queue_message(prefix + "，请注意！")
