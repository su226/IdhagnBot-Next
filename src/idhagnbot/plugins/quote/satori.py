import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.satori import Adapter, Message, MessageEvent
from nonebot.adapters.satori import Bot as SatoriBot
from nonebot.adapters.satori.element import parse
from nonebot.adapters.satori.message import RenderMessage

from idhagnbot.plugins.quote.common import (
  REPLY_EXTRACT_REGISTRY,
  USER_INFO_REGISTRY,
  MessageInfo,
  ReplyInfo,
  UserInfo,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Reply, UniMessage


async def extract_from_reply(bot: Bot, event: Event, reply: Reply) -> ReplyInfo:
  assert isinstance(bot, SatoriBot)
  assert isinstance(reply.origin, RenderMessage)
  assert isinstance(event, MessageEvent)
  message_id = reply.origin.data.get("id", "")
  message = await bot.message_get(channel_id=event.channel.id, message_id=message_id)
  assert message.created_at
  assert message.user
  content = UniMessage.of(Message.from_satori_element(parse(message.content)))
  return ReplyInfo(message.id, message.created_at, MessageInfo(message.user.id, content))


async def get_user_info(bot: Bot, event: Event, id: str) -> UserInfo:
  assert isinstance(bot, SatoriBot)
  user = await bot.user_get(user_id=id)
  name = user.nick or user.name or user.id
  avatar = user.avatar or f"avatar://{name[0]}"
  if avatar.startswith("internal:"):
    avatar = str(bot.info.api_base / "proxy" / avatar)
  return UserInfo(name, avatar)


def register() -> None:
  name = Adapter.get_name()
  REPLY_EXTRACT_REGISTRY[name] = extract_from_reply
  USER_INFO_REGISTRY[name] = get_user_info
