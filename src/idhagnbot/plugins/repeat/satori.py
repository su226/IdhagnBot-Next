import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.satori import Adapter
from nonebot.adapters.satori.event import MessageDeletedEvent, MessageEvent
from nonebot.message import event_preprocessor

from idhagnbot.context import SceneIdRaw
from idhagnbot.plugins.repeat.common import HANDLER_REGISTRY, count_recall, count_send

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, UniMessage


async def handle_recall(bot: Bot, event: MessageDeletedEvent, scene_id: SceneIdRaw) -> None:
  await count_recall(bot.adapter.get_name(), scene_id, event.message.id)


async def repeat(
  bot: Bot,
  events: list[Event],
  message: UniMessage[Segment],
  scene_id: str,
) -> None:
  event = events[0]
  if not isinstance(event, MessageEvent):
    # 可能是 InteractionCommandEvent
    return
  async with count_send(bot.adapter.get_name(), scene_id, message):
    result = await bot.message_create(
      channel_id=event.channel.id,
      content=f'<message id="{event.message.id}" forward />',
    )
    if not result:
      await message.send()


def register() -> None:
  event_preprocessor(handle_recall)
  HANDLER_REGISTRY[Adapter.get_name()] = repeat
