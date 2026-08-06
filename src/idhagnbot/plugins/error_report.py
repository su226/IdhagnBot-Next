import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from traceback import format_exception_only, format_tb
from typing import Any

from arclet import letoderea
from arclet.entari import (
    ChannelType,
    Code,
    MessageChain,
    Plugin,
    Text,
    metadata,
    plugin_config,
)
from arclet.entari.event.base import MessageEvent, SatoriEvent
from arclet.entari.scheduler import _ScheduleEvent
from arclet.letoderea import ExceptionEvent, Subscriber
from loguru import logger
from pydantic import BaseModel, Field
from satori.element import Br
from satori.exception import ActionFailed

from idhagnbot.asyncio import (
    background_exception_handler,
    create_background_task,
    delayed,
)
from idhagnbot.support import get_bot_on

__all__ = ["send_error"]


class Config(BaseModel):
    warn_interval: dict[str, timedelta | None] = Field(default_factory=dict)
    warn_filter: list[re.Pattern[str]] = Field(default_factory=list)
    warn_target: list[str] = Field(default_factory=list)
    warn_length_limit: int = 4096


@dataclass
class QueueInfo:
    date: datetime
    description: str
    exception: BaseException | str
    additional_count: int = 0


PLUGIN = Plugin.current()
metadata("", config=Config)
CONFIG = plugin_config(Config)
last_warn: dict[str, datetime] = {}
queue: dict[str, QueueInfo] = {}


async def try_send(message: MessageChain, target: str) -> None:
    platform, channel_id = target.split(":", maxsplit=1)
    bot = get_bot_on(platform)
    if bot is None:
        logger.warning(
            f"没有机器人可以发送异常消息 {brief_display(message)!r} 到 {target}",
        )
        return
    try:
        await bot.send_message(channel_id, message)
    except ActionFailed:
        logger.exception(f"发送异常消息 {brief_display(message)!r} 到 {target} 出错")


def format_exception(exception: BaseException) -> str:
    info = format_exception_only(exception)
    info.extend(format_tb(exception.__traceback__))
    return "".join(info).removesuffix("\n")


def trim_message(message: str, length: int) -> str:
    if len(message) <= length:
        return message
    return message[: length - 3] + "..."


def trim_messages(
    header: str,
    content: str,
    footer: str,
    length: int,
) -> tuple[str, str, str]:
    content_len = length
    if header_len := len(header):
        content_len -= header_len + 1
    if footer_len := len(footer):
        content_len -= footer_len + 1
    return header, trim_message(content, content_len), footer


async def send_queued_error(module_id: str) -> None:
    last_warn[module_id] = datetime.now(UTC)
    info = queue.pop(module_id)
    content = (
        info.exception
        if isinstance(info.exception, str)
        else format_exception(info.exception)
    )
    for pattern in CONFIG.warn_filter:
        if pattern.search(content):
            return
    header, content, footer = trim_messages(
        f"[{module_id}|{info.date.astimezone():%Y-%m-%d %H:%M:%S}]: {info.description}",
        content,
        f"还有 {info.additional_count} 个异常" if info.additional_count else "",
        CONFIG.warn_length_limit,
    )
    message = MessageChain([Text(header), Br(), Code(content), Br(), Text(footer)])
    await asyncio.gather(*(try_send(message, target) for target in CONFIG.warn_target))


async def send_error(
    module_id: str,
    description: str,
    exception: BaseException | str,
) -> None:
    interval = CONFIG.warn_interval.get(module_id, timedelta())
    if interval is None:
        return
    if interval:
        now = datetime.now(UTC)
        last = last_warn.get(module_id)
        if last and now < (next_date := last + interval):
            if module_id in queue:
                queue[module_id].additional_count += 1
            else:
                queue[module_id] = QueueInfo(now, description, exception)
                delayed(
                    next_date,
                    f"idhagnbot-send_queued_error-{module_id}",
                )(lambda: send_queued_error(module_id))
            return
        last_warn[module_id] = now
    content = exception if isinstance(exception, str) else format_exception(exception)
    for pattern in CONFIG.warn_filter:
        if pattern.search(content):
            return
    header, content, _ = trim_messages(
        f"[{module_id}]: {description}",
        content,
        "",
        CONFIG.warn_length_limit,
    )
    message = MessageChain([Text(header), Br(), Code(content)])
    await asyncio.gather(*(try_send(message, target) for target in CONFIG.warn_target))


def brief_display(message: MessageChain) -> str:
    display = message.display()
    if len(display) > 50:
        return f"{display[:50]}... ({len(display)})"
    return display


def send_subscriber_error(
    subscriber: Subscriber,
    event: SatoriEvent,
    exception: Exception,
) -> None:
    description = f"事件订阅者 {subscriber} 出错"
    if event.guild is not None:
        description += f"\n群组 {event.guild.name or '未知'} ({event.guild.id})"
    if event.channel is not None:
        if event.channel.type == ChannelType.DIRECT:
            channel_name = "私聊"
        else:
            channel_name = event.channel.name or "未知"
        description += f"\n频道 {channel_name} ({event.channel.id})"
    if event.user is not None:
        description += f"\n用户 {event.user.nick or '未知'} ({event.user.id})"
    if isinstance(event, MessageEvent):
        description += f"\n消息 {brief_display(event.content)!r}"
    create_background_task(send_error("command", description, exception))


@letoderea.on(ExceptionEvent)
async def on_exception(
    origin: Any,
    subscriber: Subscriber,
    exception: Exception,
) -> None:
    if isinstance(origin, _ScheduleEvent):
        create_background_task(
            send_error("scheduler", f"定时任务 {subscriber.label} 出错", exception),
        )
    elif isinstance(origin, SatoriEvent):
        send_subscriber_error(subscriber, origin, exception)
    else:
        create_background_task(
            send_error("other", f"未知订阅者 {subscriber} 出错", exception),
        )


@PLUGIN.collect
@background_exception_handler
async def _(e: BaseException, module: str, name: str) -> None:
    description = f"后台任务 {module}:{name} 出错"
    await send_error("background_task", description, e)
