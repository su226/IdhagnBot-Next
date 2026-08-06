from typing import Any

from arclet import letoderea
from arclet.entari import (
    Account,
    enter_if,
    register_internal_event,
)
from arclet.entari.event.base import InternalEvent, OriginEvent, SatoriEvent


class OneBotPokeEvent(InternalEvent):
    self_id: int
    target_id: int
    user_id: int
    group_id: int | None

    def __init__(self, account: Account, origin: OriginEvent) -> None:
        super().__init__(account, origin)
        if not origin._data:
            raise ValueError("Not an internal event.")
        self.self_id = origin._data["self_id"]
        self.target_id = origin._data["target_id"]
        self.user_id = origin._data["user_id"]
        self.group_id = origin._data.get("group_id")


@register_internal_event
def parse_onebot_poke_event(
    event_type: str,
    internal_type: str,
    internal_data: dict[str, Any],
) -> type[SatoriEvent] | None:
    if internal_type == "notice.notify.poke":
        return OneBotPokeEvent
    return None


async def check_poke_back(event: OneBotPokeEvent) -> bool:
    return event.user_id != event.self_id and event.target_id == event.self_id


@letoderea.on(OneBotPokeEvent)
@enter_if(check_poke_back)
async def handle_poke_back(account: Account, event: OneBotPokeEvent) -> None:
    if event.group_id is None:
        await account.internal(
            "friend_poke",
            user_id=event.user_id,
        )
    else:
        await account.internal(
            "group_poke",
            group_id=event.group_id,
            user_id=event.user_id,
        )
