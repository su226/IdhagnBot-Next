import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from traceback import format_exception_only
from typing import Optional, cast

import nonebot
from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
from nonebot import logger
from nonebot.exception import ActionFailed
from nonebot.matcher import Matcher
from nonebot.message import run_postprocessor
from pydantic import BaseModel, Field

from idhagnbot.asyncio import create_background_task
from idhagnbot.config import SharedConfig
from idhagnbot.target import TargetConfig

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_apscheduler")
from nonebot_plugin_alconna import Target, Text, UniMessage
from nonebot_plugin_apscheduler import scheduler

__all__ = ["send_error"]


class Config(BaseModel):
  warn_interval: dict[str, Optional[timedelta]] = Field(default_factory=dict)
  warn_target: list[TargetConfig] = Field(default_factory=list)


class Data(BaseModel):
  last_warn: dict[str, datetime] = Field(default_factory=dict)


@dataclass
class QueueInfo:
  date: datetime
  description: str
  exception: BaseException
  additional_count: int = 0


CONFIG = SharedConfig("error", Config)
last_warn = dict[str, datetime]()
queue = dict[str, QueueInfo]()


async def try_send(message: UniMessage[Text], target: Target) -> None:
  try:
    await message.send(target)
  except ActionFailed:
    logger.exception(f"发送异常消息 {message} 到 {target} 出错")


def format_exception(exception: BaseException) -> str:
  # 包括 traceback 可能会消息过长，部分平台（如 Telegram）发送不了
  return "".join(format_exception_only(None, exception)).rstrip()


async def send_queued_error(id: str) -> None:
  config = CONFIG()
  last_warn[id] = datetime.now(timezone.utc)
  info = queue.pop(id)
  message = UniMessage(
    [
      Text(f"[{id}|{info.date.astimezone():%Y-%m-%d %H:%M:%S}]: {info.description}\n"),
      Text(format_exception(info.exception)).code(),
    ],
  )
  if info.additional_count:
    message += Text(f"\n还有 {info.additional_count} 个异常")
  await asyncio.gather(*[try_send(message, target.target) for target in config.warn_target])


async def send_error(id: str, description: str, exception: BaseException) -> None:
  config = CONFIG()
  interval = config.warn_interval.get(id, timedelta())
  if interval is None:
    return
  if interval:
    now = datetime.now(timezone.utc)
    last = last_warn.get(id)
    if last and now < (next := last + interval):
      if id in queue:
        queue[id].additional_count += 1
      else:
        queue[id] = QueueInfo(now, description, exception)
        scheduler.add_job(send_queued_error, "date", (id,), run_date=next)
      return
    last_warn[id] = now
  message = UniMessage(
    [Text(f"[{id}]: {description}\n"), Text(format_exception(exception)).code()],
  )
  await asyncio.gather(*[try_send(message, target.target) for target in config.warn_target])


def on_job_error(event: JobExecutionEvent) -> None:
  create_background_task(
    send_error("scheduler", f"定时任务 {event.job_id} 失败", cast(BaseException, event.exception)),
  )


scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)


@run_postprocessor
async def _(matcher: Matcher, e: Exception) -> None:
  create_background_task(send_error("matcher", f"响应器 {matcher} 出错", e))
