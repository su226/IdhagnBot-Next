import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.telegram import Adapter
from nonebot.adapters.telegram.event import ForumTopicMessageEvent, MessageEvent

from idhagnbot.plugins.repeat.common import HANDLER_REGISTRY, count_send

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, UniMessage


async def repeat(
  bot: Bot,
  events: list[Event],
  message: UniMessage[Segment],
  scene_id: str,
) -> None:
  message_events = [event for event in events if isinstance(event, MessageEvent)]
  chat_id = message_events[0].chat.id
  message_thread_id = (
    events[0].message_thread_id if isinstance(events[0], ForumTopicMessageEvent) else None
  )
  with count_send(bot.adapter.get_name(), scene_id, message):
    await bot.forward_messages(
      chat_id=chat_id,
      message_thread_id=message_thread_id,
      from_chat_id=chat_id,
      message_ids=[event.message_id for event in message_events],
    )


def register() -> None:
  HANDLER_REGISTRY[Adapter.get_name()] = repeat
