import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent
from nonebot.adapters.onebot.v11 import Bot as OBBot
from nonebot.adapters.onebot.v11.event import Reply as OBReply

from idhagnbot.plugins.interaction.common import AT_EXTRACT_REGISTRY, REPLY_EXTRACT_REGISTRY

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import At, Reply


async def extract_from_reply(bot: Bot, event: Event, reply: Reply) -> str:
  assert isinstance(bot, OBBot)
  assert isinstance(reply.origin, OBReply)
  user_id = reply.origin.sender.user_id
  assert user_id
  if isinstance(event, GroupMessageEvent):
    info = await bot.get_group_member_info(group_id=event.group_id, user_id=user_id)
    return info["card"] or info["nickname"]
  info = await bot.get_stranger_info(user_id=user_id)
  return info["nickname"]


async def extract_from_at(bot: Bot, event: Event, at: At) -> str:
  if at.display:
    return at.display
  user_id = int(at.target)
  if isinstance(event, GroupMessageEvent):
    info = await bot.get_group_member_info(group_id=event.group_id, user_id=user_id)
    return info["card"] or info["nickname"]
  info = await bot.get_stranger_info(user_id=user_id)
  return info["nickname"]


def register() -> None:
  adapter = Adapter.get_name()
  REPLY_EXTRACT_REGISTRY[adapter] = extract_from_reply
  AT_EXTRACT_REGISTRY[adapter] = extract_from_at
