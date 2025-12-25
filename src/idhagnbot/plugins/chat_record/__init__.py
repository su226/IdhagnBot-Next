from datetime import datetime
from typing import Any, ClassVar

import nonebot
from nonebot.adapters import Bot
from nonebot.matcher import current_event
from nonebot.message import event_preprocessor
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.context import SceneId, UserId, get_bot_id, get_target_id
from idhagnbot.hook import on_message_sent
from idhagnbot.hook.common import SentMessage
from idhagnbot.message import EventTime, MessageId, OrigUniMsg
from idhagnbot.message.common import message_id

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
from nonebot_plugin_alconna import Segment, Target, UniMessage
from nonebot_plugin_orm import Model, get_session


class Message(Model):
  __tablename__: ClassVar[Any] = "idhagnbot_chat_record_message"
  record_id: Mapped[int] = mapped_column(primary_key=True)
  time: Mapped[datetime]
  scene_id: Mapped[str]
  user_id: Mapped[str]
  message_id: Mapped[str]
  content: Mapped[str]
  outgoing: Mapped[bool] = mapped_column(server_default="0")
  caused_by: Mapped[str | None]


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
        outgoing=False,
        caused_by=None,
      ),
    )
    await sql.commit()


@on_message_sent
async def _(
  bot: Bot,
  original_message: UniMessage[Segment],
  messages: list[SentMessage],
  target: Target,
) -> None:
  self_id = await get_bot_id(bot)
  scene_id = await get_target_id(target)
  event = current_event.get(None)
  caused_by = await message_id(bot, event) if event else None
  async with get_session() as sql:
    for message in messages:
      sql.add(
        Message(
          time=message.time,
          scene_id=scene_id,
          user_id=self_id,
          message_id=message.id,
          content=message.content.dump(media_save_dir=False, json=True),
          outgoing=True,
          caused_by=caused_by,
        ),
      )
    await sql.commit()
