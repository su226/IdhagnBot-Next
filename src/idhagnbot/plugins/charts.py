from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import nonebot
from anyio.to_thread import run_sync
from nonebot.adapters import Bot
from PIL import Image, ImageOps
from sqlalchemy import func, select

from idhagnbot.asyncio import gather_seq
from idhagnbot.command import CommandBuilder
from idhagnbot.context import SceneId, get_member, get_user
from idhagnbot.datetime import DATE_ARGS_USAGE, parse_date_range
from idhagnbot.image import (
  get_scale_resample,
  normalize_url,
  open_url,
  resize_height,
  to_segment,
)
from idhagnbot.image.bar_chart import (
  DEFAULT_STRIPE_PATTERN,
  BarChart,
  ColumnChart,
  Item,
  material_palette_from_icon,
  material_pattern_stripe_from_icon,
)

if TYPE_CHECKING:
  from sqlalchemy.ext.asyncio import AsyncEngine

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
nonebot.require("idhagnbot.plugins.chat_record")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta
from nonebot_plugin_alconna import Image as ImageSeg
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_uninfo import Interface, QryItrface, Scene, Uninfo

from idhagnbot.plugins.chat_record import MatcherCall, Message


async def open_avatar(url: str | None, bot: Bot) -> Image.Image | None:
  return await open_url(normalize_url(url, bot)) if url else None


async def get_name_and_avatar(
  interface: Interface,
  scene: Scene,
  user_id: str,
) -> tuple[str, Image.Image | None]:
  if member := await get_member(interface, scene, user_id):
    name = member.nick or member.user.nick or member.user.name or member.user.id
    return name, await open_avatar(member.user.avatar, interface.bot)
  if user := await get_user(interface, user_id):
    name = user.nick or user.name or user.id
    return name, await open_avatar(user.avatar, interface.bot)
  return user_id, None


leaderboard = (
  CommandBuilder()
  .node("charts.leaderboard")
  .parser(
    Alconna(
      "leaderboard",
      Args["start?", str, None],
      Args["end?", str, None],
      meta=CommandMeta("查看最近的发言排行", usage=DATE_ARGS_USAGE),
    ),
  )
  .aliases(
    {
      "rank": None,
      "排名": "zh-CN",
      "排行": "zh-CN",
    },
  )
  .build()
)


@leaderboard.handle()
async def _(
  start: str | None,
  end: str | None,
  scene_id: SceneId,
  sql: async_scoped_session,
  session: Uninfo,
  interface: QryItrface,
) -> None:
  start_date, end_date = parse_date_range(start, end)
  result = await sql.execute(
    select(Message.user_id, count := func.count(Message.user_id))
    .where(
      Message.scene_id == scene_id,
      Message.time >= start_date,
      Message.time <= end_date,
      ~Message.outgoing,
    )
    .group_by(Message.user_id)
    .order_by(count.desc())
    .limit(20),
  )
  result = result.all()
  end_date -= timedelta(seconds=1)  # 显示 23:59:59 而不是 00:00:00，以防误会
  if not result:
    await leaderboard.finish(
      f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 内没有数据",
    )
  names_and_avatars = await gather_seq(
    get_name_and_avatar(interface, session.scene, user_id) for user_id, _ in result
  )

  def make() -> ImageSeg:
    chart = BarChart()
    chart.title = (
      f"{session.scene.name}\n"
      f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 的排行"
    )
    chart.integral_splits = True
    items = list[Item]()
    for (_, count), (name, avatar) in zip(result, names_and_avatars, strict=True):
      avatar1 = avatar
      if avatar1 is not None:
        avatar1 = resize_height(avatar1, chart.bar_width)
        palette = material_palette_from_icon(avatar1)
      else:
        avatar1 = None
        palette = None
      items.append(Item(count, name=name, icon=avatar1, palette=palette))
    chart.extend(items)
    return to_segment(chart.render())

  await leaderboard.finish(await run_sync(make))


command_leaderboard = (
  CommandBuilder()
  .node("charts.command_leaderboard")
  .parser(
    Alconna(
      "command_leaderboard",
      Args["start?", str, None],
      Args["end?", str, None],
      meta=CommandMeta("查看最近的命令调用排行", usage=DATE_ARGS_USAGE),
    ),
  )
  .aliases(
    {
      "command_rank": None,
      "命令排名": "zh-CN",
      "命令排行": "zh-CN",
    },
  )
  .build()
)


@command_leaderboard.handle()
async def _(
  start: str | None,
  end: str | None,
  scene_id: SceneId,
  sql: async_scoped_session,
  session: Uninfo,
  bot: Bot,
) -> None:
  start_date, end_date = parse_date_range(start, end)
  result = await sql.execute(
    select(MatcherCall.command_name, count := func.count(MatcherCall.command_name))
    .where(
      MatcherCall.scene_id == scene_id,
      MatcherCall.time >= start_date,
      MatcherCall.time <= end_date,
    )
    .group_by(MatcherCall.command_name)
    .having(MatcherCall.command_name.isnot(None))
    .order_by(count.desc())
    .limit(20),
  )
  result = result.all()
  end_date -= timedelta(seconds=1)  # 显示 23:59:59 而不是 00:00:00，以防误会
  if not result:
    await command_leaderboard.finish(
      f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 内没有数据",
    )
  avatar = (
    await open_url(
      normalize_url(session.scene.avatar, bot),
      process=lambda im: ImageOps.fit(im, (64, 64), get_scale_resample()),
    )
    if session.scene.avatar
    else None
  )

  def make() -> ImageSeg:
    chart = BarChart([Item(count, name=command) for command, count in result])
    chart.title = (
      f"{session.scene.name}\n"
      f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 的命令排行"
    )
    chart.integral_splits = True
    chart.pattern = material_pattern_stripe_from_icon(avatar) if avatar else DEFAULT_STRIPE_PATTERN
    return to_segment(chart.render())

  await command_leaderboard.finish(await run_sync(make))


hourly_statistics = (
  CommandBuilder()
  .node("charts.hourly_statistics")
  .parser(
    Alconna(
      "hourly_statistics",
      meta=CommandMeta("查看最近 7 天的消息统计，以小时为单位"),
    ),
  )
  .aliases({"小时统计": "zh-CN"})
  .build()
)


@hourly_statistics.handle()
async def _(
  scene_id: SceneId,
  sql: async_scoped_session,
  session: Uninfo,
  bot: Bot,
) -> None:
  end_date = datetime.now()
  end_date = end_date.replace(hour=end_date.hour + 1, minute=0, second=0, microsecond=0)
  start_date = end_date - timedelta(7)
  engine: AsyncEngine = sql.session_factory.kw["bind"]
  if engine.dialect.name == "sqlite":
    date_func = func.strftime("%Y-%m-%d %H:00:00", Message.time)
  elif engine.dialect.name == "mysql":
    date_func = func.date_format(Message.time, "%Y-%m-%d %H:00:00")
  elif engine.dialect.name == "postgresql":
    date_func = func.date_trunc("hour", Message.time)
  else:
    raise NotImplementedError(f"不支持的数据库: {engine.dialect.name}")
  result = await sql.execute(
    select(date_func, func.count(Message.record_id))
    .where(
      Message.scene_id == scene_id,
      Message.time >= start_date,
      Message.time <= end_date,
    )
    .group_by(date_func)
    .order_by(date_func),
  )
  result = result.all()
  end_date -= timedelta(seconds=1)  # 显示 x:59:59 而不是 x+1:00:00，以防误会
  avatar = (
    await open_url(
      normalize_url(session.scene.avatar, bot),
      process=lambda im: ImageOps.fit(im, (64, 64), get_scale_resample()),
    )
    if session.scene.avatar
    else None
  )

  def make() -> ImageSeg:
    items = list[float]()
    current = start_date
    i = 0
    while current <= end_date:
      if i < len(result) and str(result[i][0]) == str(current):
        items.append(result[i][1])
        i += 1
      else:
        items.append(0)
      current += timedelta(hours=1)
    chart = ColumnChart(items)
    chart.title = (
      f"{session.scene.name}\n"
      f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 的统计"
    )
    chart.bar_width = 8
    chart.integral_splits = True
    chart.pattern = material_pattern_stripe_from_icon(avatar) if avatar else DEFAULT_STRIPE_PATTERN
    chart.show_values = False
    return to_segment(chart.render())

  await leaderboard.finish(await run_sync(make))
