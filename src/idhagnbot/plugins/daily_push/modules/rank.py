from datetime import date, timedelta

import nonebot
from sqlalchemy import desc, func, select

from idhagnbot.asyncio import gather_seq
from idhagnbot.context import get_target_id
from idhagnbot.plugins.daily_push.module import TargetAwareModule

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
nonebot.require("idhagnbot.plugins.chat_record")
from nonebot_plugin_alconna import Segment, Target, Text, UniMessage
from nonebot_plugin_orm import get_session
from nonebot_plugin_uninfo import SceneType, get_interface

from idhagnbot.plugins.chat_record import Message

EMOJIS = ["🥇", "🥈", "🥉"]


class RankModule(TargetAwareModule):
  async def format(self, target: Target) -> list[UniMessage[Segment]]:
    if target.private:
      return []
    scene_id = await get_target_id(target)
    today = date.today()
    yesterday = today - timedelta(1)
    async with get_session() as sql:
      result = await sql.execute(
        select(
          Message.user_id,
          count_func := func.count(Message.user_id),
        )
        .where(
          Message.scene_id == scene_id,
          Message.time >= yesterday,
          Message.time < today,
        )
        .group_by(Message.user_id)
        .order_by(desc(count_func))
        .limit(10),
      )
    if not result:
      return []
    result = list(result)
    bot = await target.select()
    interface = get_interface(bot)
    if not interface:
      return []
    lines = ["昨天最能水的成员："]
    if target.channel:
      scene_type = SceneType.GUILD
      scene_id = target.parent_id
    else:
      scene_type = SceneType.GROUP
      scene_id = target.id
    infos = await gather_seq(
      interface.get_member(scene_type, scene_id, user_id) for user_id, _ in result
    )
    for i, ((user_id, count), info) in enumerate(zip(result, infos)):
      prefix = EMOJIS[i] if i < len(EMOJIS) else f"{i + 1}."
      nickname = info.nick or info.user.nick or info.user.name or info.user.id if info else user_id
      lines.append(f"{prefix} {nickname} - {count} 条")
    return [UniMessage(Text("\n".join(lines)))]
