import asyncio
from dataclasses import dataclass
from datetime import timedelta

from arclet.entari import Text, metadata, plugin_config
from loguru import logger
from pydantic import BaseModel, Field
from satori.exception import ActionFailed

from idhagnbot.support import get_bot_on


class Config(BaseModel):
    targets: list[str] = Field(default_factory=list)
    disconnect_grace_time: timedelta = timedelta(seconds=10)


@dataclass
class QueuedMessage:
    message: str
    targets: list[str]


metadata("", config=Config)
CONFIG = plugin_config(Config)
queued_messages: list[QueuedMessage] = []
lock = asyncio.Lock()  # 防止多个机器人同时上线时出错（尤其是启动时）


async def queue_message(message: str) -> None:
    queued_messages.append(QueuedMessage(message, CONFIG.targets.copy()))
    await send_queued_messages()


async def send_queued_messages() -> None:
    async with lock:
        hit_messages = list[QueuedMessage]()
        for message in queued_messages:
            hit_targets = list[str]()
            for target in message.targets:
                platform, channel_id = target.split(":", maxsplit=1)
                bot = get_bot_on(platform)
                if bot is None:
                    continue
                hit_targets.append(target)
                try:
                    await bot.send_message(channel_id, [Text(message.message)])
                except ActionFailed:
                    logger.exception(f"消息发送失败：{bot} {message.message}")
            for target in hit_targets:
                message.targets.remove(target)
            if not message.targets:
                hit_messages.append(message)
        for message in hit_messages:
            queued_messages.remove(message)
