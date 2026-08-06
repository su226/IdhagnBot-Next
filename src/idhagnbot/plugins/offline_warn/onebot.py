from typing import Any

from arclet import letoderea
from arclet.entari import Account
from arclet.entari.event.base import (
    InternalEvent,
    OriginEvent,
    SatoriEvent,
    register_internal_event,
)
from loguru import logger

from idhagnbot.plugins.offline_warn.common import queue_message


class NapCatOfflineEvent(InternalEvent):
    """NapCat / SnowLuma 的掉线事件"""

    self_id: int
    tag: str
    message: str

    def __init__(self, account: Account, origin: OriginEvent) -> None:
        super().__init__(account, origin)
        if not origin._data:
            raise ValueError("Not an internal event.")
        self.self_id = origin._data["self_id"]
        self.tag = origin._data["tag"]
        self.message = origin._data["message"]


@register_internal_event
def parse_napcat_offline_event(
    event_type: str,
    internal_type: str,
    internal_data: dict[str, Any],
) -> type[SatoriEvent] | None:
    if internal_type == "notice.bot_offline":
        return NapCatOfflineEvent
    return None


@letoderea.on(NapCatOfflineEvent)
async def handle_offline(event: NapCatOfflineEvent) -> None:
    now_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    tag = event.tag
    message = event.message
    prefix = f"后端 OneBot V11 {event.self_id} 在 {now_str} 左右下线，{tag=} {message=}"
    logger.warning(prefix + "，将发送警告！")
    await queue_message(prefix + "，请注意！")
