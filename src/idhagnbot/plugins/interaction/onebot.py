import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent
from nonebot.adapters.onebot.v11 import Bot as OBBot
from nonebot.adapters.onebot.v11.event import Reply as OBReply

from idhagnbot.plugins.interaction.common import REPLY_EXTRACT_REGISTRY

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Reply


async def extract(bot: Bot, event: Event, reply: Reply) -> str:
  assert isinstance(bot, OBBot)
  assert isinstance(reply.origin, OBReply)
  user_id = reply.origin.sender.user_id
  assert user_id
  if isinstance(event, GroupMessageEvent):
    info = await bot.get_group_member_info(group_id=event.group_id, user_id=user_id)
    return info["card"] or info["nickname"]
  info = await bot.get_stranger_info(user_id=user_id)
  return info["nickname"]


def register() -> None:
  REPLY_EXTRACT_REGISTRY[Adapter.get_name()] = extract
