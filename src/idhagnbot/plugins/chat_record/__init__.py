from datetime import datetime
from typing import Any, ClassVar

import nonebot
from nonebot.message import event_preprocessor
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.context import SceneId, UserId
from idhagnbot.message import EventTime, MessageId, OrigUniMsg

nonebot.require("nonebot_plugin_orm")
from nonebot_plugin_orm import Model, get_session


class Message(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_chat_record_message"
  record_id: Mapped[int] = mapped_column(primary_key=True)
  time: Mapped[datetime]
  scene_id: Mapped[str]
  user_id: Mapped[str]
  message_id: Mapped[str]
  content: Mapped[str]


@event_preprocessor
async def _(
  event_time: EventTime,
  scene_id: SceneId,
  user_id: UserId,
  message_id: MessageId,
  message: OrigUniMsg,
) -> None:
  async with get_session() as sql:
    sql.add(
      Message(
        time=event_time,
        scene_id=scene_id,
        user_id=user_id,
        message_id=message_id,
        content=message.dump(media_save_dir=False, json=True),
      ),
    )
    await sql.commit()
