from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from traceback import format_exception_only, format_tb
from typing import cast

import nonebot
from apscheduler.events import (  # pyright: ignore[reportMissingTypeStubs]
  EVENT_JOB_ERROR,
  JobExecutionEvent,
)
from nonebot import logger
from nonebot.exception import ActionFailed, NetworkError
from nonebot.matcher import Matcher
from nonebot.message import run_postprocessor
from pydantic import BaseModel, Field

from idhagnbot.asyncio import background_exception_handler, create_background_task, gather_seq
from idhagnbot.config import SharedConfig
from idhagnbot.target import TargetConfig

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_apscheduler")
from nonebot_plugin_alconna import SerializeFailed, Target, Text, UniMessage
from nonebot_plugin_apscheduler import scheduler

__all__ = ["send_error"]


class Config(BaseModel):
  warn_interval: dict[str, timedelta | None] = Field(default_factory=dict)
  warn_target: list[TargetConfig] = Field(default_factory=list)
  warn_length_limit: int = 4096


class Data(BaseModel):
  last_warn: dict[str, datetime] = Field(default_factory=dict)


@dataclass
class QueueInfo:
  date: datetime
  description: str
  exception: BaseException | str
  additional_count: int = 0


CONFIG = SharedConfig("error", Config)
last_warn = dict[str, datetime]()
queue = dict[str, QueueInfo]()


async def try_send(message: UniMessage[Text], target: Target) -> None:
  try:
    await message.send(target)
  except (ActionFailed, NetworkError, SerializeFailed):
    logger.exception(f"发送异常消息 {message!r} 到 {target} 出错")


def format_exception(exception: BaseException) -> str:
  info = format_exception_only(exception)
  info.extend(format_tb(exception.__traceback__))
  return "".join(info).removesuffix("\n")


def trim_message(message: str, length: int) -> str:
  if len(message) <= length:
    return message
  return message[: length - 3] + "..."


def trim_messages(header: str, content: str, footer: str, length: int) -> tuple[str, str, str]:
  return header, trim_message(content, length - len(header) - len(footer)), footer


async def send_queued_error(module_id: str) -> None:
  config = CONFIG()
  last_warn[module_id] = datetime.now(timezone.utc)
  info = queue.pop(module_id)
  header, content, footer = trim_messages(
    f"[{module_id}|{info.date.astimezone():%Y-%m-%d %H:%M:%S}]: {info.description}\n",
    info.exception if isinstance(info.exception, str) else format_exception(info.exception),
    f"\n还有 {info.additional_count} 个异常" if info.additional_count else "",
    config.warn_length_limit,
  )
  message = UniMessage([Text(header), Text(content).code(), Text(footer)])
  await gather_seq(try_send(message, target.target) for target in config.warn_target)


async def send_error(module_id: str, description: str, exception: BaseException | str) -> None:
  config = CONFIG()
  interval = config.warn_interval.get(module_id, timedelta())
  if interval is None:
    return
  if interval:
    now = datetime.now(timezone.utc)
    last = last_warn.get(module_id)
    if last and now < (next_date := last + interval):
      if module_id in queue:
        queue[module_id].additional_count += 1
      else:
        queue[module_id] = QueueInfo(now, description, exception)
        scheduler.add_job(send_queued_error, "date", (module_id,), run_date=next_date)
      return
    last_warn[module_id] = now
  header, content, _ = trim_messages(
    f"[{module_id}]: {description}\n",
    exception if isinstance(exception, str) else format_exception(exception),
    "",
    config.warn_length_limit,
  )
  message = UniMessage([Text(header), Text(content).code()])
  await gather_seq(try_send(message, target.target) for target in config.warn_target)


def on_job_error(event: JobExecutionEvent) -> None:
  exception = "".join(format_exception_only(cast(BaseException, event.exception)))
  exception += cast(str, event.traceback).removesuffix("\n")
  create_background_task(send_error("scheduler", f"定时任务 {event.job_id} 失败", exception))


scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)


@run_postprocessor
async def _(matcher: Matcher, e: Exception) -> None:
  create_background_task(send_error("matcher", f"响应器 {matcher} 出错", e))


@background_exception_handler
async def _(e: Exception) -> None:
  description = "后台任务出错"
  logger.opt(exception=e).error(description)
  await send_error("background_task", description, e)
