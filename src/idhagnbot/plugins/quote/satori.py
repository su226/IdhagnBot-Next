import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.satori import Adapter
from nonebot.adapters.satori import Bot as SatoriBot

from idhagnbot.image import normalize_url
from idhagnbot.plugins.quote.common import (
  USER_INFO_REGISTRY,
  UserInfo,
)

nonebot.require("nonebot_plugin_alconna")


async def get_user_info(bot: Bot, event: Event, user_id: str) -> UserInfo:
  assert isinstance(bot, SatoriBot)
  user = await bot.user_get(user_id=user_id)
  name = user.nick or user.name or user.id
  avatar = normalize_url(user.avatar, bot) if user.avatar else f"avatar://{name[0]}"
  return UserInfo(name, avatar)


def register() -> None:
  name = Adapter.get_name()
  USER_INFO_REGISTRY[name] = get_user_info
