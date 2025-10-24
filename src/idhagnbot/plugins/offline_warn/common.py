import asyncio
from dataclasses import dataclass

import nonebot
from nonebot import logger
from nonebot.adapters import Bot
from nonebot.exception import ActionFailed
from pydantic import BaseModel, Field

from idhagnbot.config import SharedConfig
from idhagnbot.target import TargetConfig

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_apscheduler")
nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_alconna import SerializeFailed, Target, UniMessage


class Config(BaseModel):
  targets: list[TargetConfig] = Field(default_factory=list)


@dataclass
class QueuedMessage:
  message: str
  targets: list[TargetConfig]


CONFIG = SharedConfig("offline_warn", Config)
queued_messages = list[QueuedMessage]()
lock = asyncio.Lock()  # 防止多个机器人同时上线时出错（尤其是启动时）


async def queue_message(message: str) -> None:
  config = CONFIG()
  queued_messages.append(QueuedMessage(message, config.targets.copy()))
  await send_queued_messages()


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
          logger.exception(f"消息发送失败：{bot} {message.message}")
      for target in hit_targets:
        message.targets.remove(target)
      if not message.targets:
        hit_messages.append(message)
    for message in hit_messages:
      queued_messages.remove(message)
