import nonebot
from nonebot.adapters import Bot, Event
from nonebot.adapters.satori import Adapter
from nonebot.adapters.satori import Bot as SatoriBot

from idhagnbot.plugins.quote.common import (
  USER_INFO_REGISTRY,
  UserInfo,
)

nonebot.require("nonebot_plugin_alconna")


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
  USER_INFO_REGISTRY[name] = get_user_info
