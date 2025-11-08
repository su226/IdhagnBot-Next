import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.satori import Adapter
from nonebot.adapters.satori.event import MessageDeletedEvent, MessageEvent
from nonebot.message import event_preprocessor

from idhagnbot.context import SceneIdRaw
from idhagnbot.message import UniMsg
from idhagnbot.plugins.repeat.common import HANDLER_REGISTRY, LastMessage, is_same, last_messages

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, UniMessage


async def handle_recall(
  bot: Bot,
  event: MessageDeletedEvent,
  scene_id: SceneIdRaw,
  message: UniMsg,
) -> None:
  if (last := last_messages.get(scene_id)) and is_same(
    bot.adapter.get_name(),
    last.message,
    message,
  ):
    if event.user.id == event.login.identity:
      last = last_messages[scene_id] = LastMessage(
        message=message,
        received_count=last.received_count,
        sending_count=last.sending_count,
        sent_count=last.sent_count - 1,
      )
    else:
      last = last_messages[scene_id] = LastMessage(
        message=message,
        received_count=last.received_count - 1,
        sending_count=last.sending_count,
        sent_count=last.sent_count,
      )


async def repeat(
  bot: Bot,
  events: list[Event],
  message: UniMessage[Segment],
  scene_id: str,
) -> None:
  event = events[0]
  assert isinstance(event, MessageEvent)
  result = await bot.message_create(
    channel_id=event.channel.id,
    content=f'<message id="{event.message.id}" forward />',
  )
  if not result:
    await message.send()


def register() -> None:
  event_preprocessor(handle_recall)
  HANDLER_REGISTRY[Adapter.get_name()] = repeat
