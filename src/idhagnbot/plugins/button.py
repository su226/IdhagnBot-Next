import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from arclet import letoderea
from arclet.entari import Channel, MessageObject, User
from arclet.entari.event.base import InteractionButtonEvent
from entari_plugin_database import (
    AsyncSession,
    Base,
    Mapped,
    get_session,
    mapped_column,
)  # entari: plugin
from sqlalchemy import delete

from idhagnbot.asyncio import delayed


class Button(Base):
    __tablename__ = "idhagnbot_button_button"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    channel_id: Mapped[str]
    user_id: Mapped[str]
    message_id: Mapped[str]
    type: Mapped[str]
    data: Mapped[str]
    expire_at: Mapped[datetime | None]


@letoderea.make_event(name="idhagnbot/managed_button")
class ManagedButtonEvent:
    origin: InteractionButtonEvent
    channel: Channel
    user: User
    message: MessageObject
    type: str
    data: Any
    expire_at: datetime | None


@letoderea.on(InteractionButtonEvent)
async def handle_button(event: InteractionButtonEvent, db: AsyncSession) -> None:
    if event.channel is None or event.user is None or event.message is None:
        return
    try:
        uuid = UUID(event.button.id)
    except ValueError:
        return
    data = await db.get(Button, uuid)
    if (
        data is None
        or data.channel_id != event.channel.id
        or data.user_id != event.user.id
        or data.message_id != event.message.id
        or (data.expire_at is not None and datetime.now() > data.expire_at)
    ):
        return
    managed = ManagedButtonEvent(
        event,
        event.channel,
        event.user,
        event.message,
        data.type,
        json.loads(data.data),
        data.expire_at,
    )
    await letoderea.publish(managed)


async def expire_button(button_id: UUID) -> None:
    async with get_session() as db:
        await db.execute(delete(Button).where(Button.id == button_id))


async def register_button(
    button_id: UUID,
    channel_id: str,
    user_id: str,
    message_id: str,
    button_type: str,
    data: Any,
    expire: datetime | timedelta | None = None,
) -> None:
    expire_at = datetime.now() + expire if isinstance(expire, timedelta) else expire
    async with get_session() as db:
        button = Button(
            id=button_id,
            channel_id=channel_id,
            user_id=user_id,
            message_id=message_id,
            type=button_type,
            data=json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            expire_at=expire_at,
        )
        await db.merge(button)
        await db.commit()
    if expire_at is not None:
        delayed(expire_at, label=f"idhagnbot-expire_button-{button_id}")(
            lambda: expire_button(button_id),
        )
