import re
from collections.abc import Generator
from datetime import datetime, timedelta

import nonebot
from anyio.to_thread import run_sync
from nonebot.adapters import Bot, Event
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.asyncio import gather_seq
from idhagnbot.command import COMMAND_LIKE_KEY, CommandBuilder
from idhagnbot.config import Reloadable, SharedConfig
from idhagnbot.context import SceneId, SceneIdRaw, get_member, get_user
from idhagnbot.datetime import DATE_ARGS_USAGE, parse_date_range
from idhagnbot.image import get_scale_resample, normalize_url, open_url, resize_height, to_segment
from idhagnbot.image.bar_chart import (
  DEFAULT_STRIPE_PATTERN,
  BarChart,
  Item,
  material_palette_from_icon,
  material_pattern_stripe_from_icon,
)
from idhagnbot.message import EventTime, UniMsg

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, UniMessage
from nonebot_plugin_alconna import Image as ImageSeg
from nonebot_plugin_orm import Model, async_scoped_session
from nonebot_plugin_uninfo import Interface, QryItrface, Scene, Uninfo


class Counter(BaseModel):
  id: str
  name: str
  patterns: list[re.Pattern[str]]
  exclude: list[re.Pattern[str]] = Field(default_factory=list)
  match_rank: bool = False
  group: int | str = Field(default=0)


class Config(BaseModel):
  counters: list[Counter] = Field(default_factory=list)


class Counted(Model):
  __tablename__ = "idhagnbot_regex_counter_counted"
  id: Mapped[int] = mapped_column(primary_key=True)
  time: Mapped[datetime]
  scene_id: Mapped[str]
  counter_id: Mapped[str]
  user_id: Mapped[str]
  match: Mapped[str]


CONFIG = SharedConfig("regex_counter", Config, Reloadable.EAGER)
matchers = list[type[Matcher]]()
driver = nonebot.get_driver()


@driver.on_startup
async def _() -> None:
  CONFIG()


@CONFIG.onload
def _(prev: Config | None, curr: Config) -> None:
  for matcher in matchers:
    matcher.destroy()
  matchers.clear()
  for counter in curr.counters:
    matchers.extend(register(counter))


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


def register(counter: Counter) -> Generator[type[Matcher], None, None]:
  async def check_count(event: Event, message: UniMsg, state: T_State) -> bool:
    try:
      event.get_user_id()
    except (ValueError, NotImplementedError):
      return False
    if state.get(COMMAND_LIKE_KEY):
      return False
    text = message.extract_plain_text()
    matches = list[str]()
    for pattern in counter.patterns:
      for match in pattern.finditer(text):
        content = match[counter.group]
        excluded = False
        for exclude_pattern in counter.exclude:
          if exclude_pattern.search(content):
            excluded = True
            break
        if not excluded:
          matches.append(content)
    if matches:
      state["counter"] = counter
      state["matches"] = matches
      return True
    return False

  async def handle_count(
    event: Event,
    state: T_State,
    scene_id: SceneIdRaw,
    sql: async_scoped_session,
    event_time: EventTime,
  ) -> None:
    counter: Counter = state["counter"]
    matches: list[str] = state["matches"]
    user_id = event.get_user_id()
    for match in matches:
      sql.add(
        Counted(
          time=event_time,
          scene_id=scene_id,
          counter_id=counter.id,
          user_id=user_id,
          match=match,
        ),
      )
    await sql.commit()

  yield nonebot.on_message(check_count, handlers=[handle_count])

  async def handle_group_statistics(
    start: str | None,
    end: str | None,
    session: Uninfo,
    scene_id: SceneId,
    state: T_State,
    sql: async_scoped_session,
  ) -> None:
    counter: Counter = state["counter"]
    start_date, end_date = parse_date_range(start, end)
    result = await sql.execute(
      select(func.count())
      .select_from(Counted)
      .where(
        Counted.scene_id == scene_id,
        Counted.counter_id == counter.id,
        Counted.time >= start_date,
        Counted.time <= end_date,
      ),
    )
    count = result.scalar_one()
    end_date -= timedelta(seconds=1)
    await UniMessage(
      f"{session.scene.name} 内 {start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} "
      f"的{counter.name}次数为 {count}。",
    ).send()

  matcher = (
    CommandBuilder()
    .node(f"regex_counter.{counter.id}.statistics.group")
    .parser(
      Alconna(
        f"群{counter.name}统计",
        Args["start?", str, None],
        Args["end?", str, None],
        meta=CommandMeta(f"群内总{counter.name}次数统计", usage=DATE_ARGS_USAGE),
      ),
    )
    .state({"counter": counter})
    .build()
  )
  matcher.handle()(handle_group_statistics)
  yield matcher

  async def handle_user_statistics(
    start: str | None,
    end: str | None,
    event: Event,
    session: Uninfo,
    scene_id: SceneId,
    state: T_State,
    sql: async_scoped_session,
  ) -> None:
    counter: Counter = state["counter"]
    user_id = event.get_user_id()
    start_date, end_date = parse_date_range(start, end)
    result = await sql.execute(
      select(func.count())
      .select_from(Counted)
      .where(
        Counted.scene_id == scene_id,
        Counted.user_id == user_id,
        Counted.counter_id == counter.id,
        Counted.time >= start_date,
        Counted.time <= end_date,
      ),
    )
    count = result.scalar_one()
    end_date -= timedelta(seconds=1)
    if session.member and session.member.nick:
      member_name = session.member.nick
    else:
      member_name = session.user.nick or session.user.name or session.user.id
    await UniMessage(
      f"{member_name} 在 {session.scene.name} 内 {start_date:%Y-%m-%d %H:%M:%S} 到 "
      f"{end_date:%Y-%m-%d %H:%M:%S} 的{counter.name}次数为 {count}。",
    ).send()

  matcher = (
    CommandBuilder()
    .node(f"regex_counter.{counter.id}.statistics.user")
    .parser(
      Alconna(
        f"个人{counter.name}统计",
        Args["start?", str, None],
        Args["end?", str, None],
        meta=CommandMeta(f"个人{counter.name}次数统计", usage=DATE_ARGS_USAGE),
      ),
    )
    .state({"counter": counter})
    .build()
  )
  matcher.handle()(handle_user_statistics)
  yield matcher

  async def handle_user_rank(
    start: str | None,
    end: str | None,
    session: Uninfo,
    scene_id: SceneId,
    state: T_State,
    interface: QryItrface,
    sql: async_scoped_session,
  ) -> None:
    counter: Counter = state["counter"]
    start_date, end_date = parse_date_range(start, end)
    result = await sql.execute(
      select(Counted.user_id, count := func.count(Counted.user_id))
      .where(
        Counted.scene_id == scene_id,
        Counted.counter_id == counter.id,
        Counted.time >= start_date,
        Counted.time <= end_date,
      )
      .group_by(Counted.user_id)
      .order_by(count.desc())
      .limit(20),
    )
    result = result.all()
    end_date -= timedelta(seconds=1)
    if not result:
      await UniMessage(
        f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 内没有数据",
      ).finish()
    names_and_avatars = await gather_seq(
      get_name_and_avatar(interface, session.scene, user_id) for user_id, _ in result
    )

    def make() -> ImageSeg:
      chart = BarChart()
      chart.title = (
        f"{session.scene.name}\n{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} "
        f"的{counter.name}次数排行"
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

    await UniMessage(await run_sync(make)).send()

  matcher = (
    CommandBuilder()
    .node(f"regex_counter.{counter.id}.rank")
    .parser(
      Alconna(
        f"{counter.name}排行",
        Args["start?", str, None],
        Args["end?", str, None],
        meta=CommandMeta(f"群内总{counter.name}次数按群成员排行", usage=DATE_ARGS_USAGE),
      ),
    )
    .state({"counter": counter})
    .build()
  )
  matcher.handle()(handle_user_rank)
  yield matcher

  if counter.match_rank:

    async def handle_match_rank_group(
      start: str | None,
      end: str | None,
      session: Uninfo,
      scene_id: SceneId,
      state: T_State,
      sql: async_scoped_session,
      bot: Bot,
    ) -> None:
      counter: Counter = state["counter"]
      start_date, end_date = parse_date_range(start, end)
      result = await sql.execute(
        select(Counted.match, count := func.count(Counted.match))
        .where(
          Counted.scene_id == scene_id,
          Counted.counter_id == counter.id,
          Counted.time >= start_date,
          Counted.time <= end_date,
        )
        .group_by(Counted.match)
        .order_by(count.desc())
        .limit(20),
      )
      result = result.all()
      end_date -= timedelta(seconds=1)
      if not result:
        await UniMessage(
          f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 内没有数据",
        ).finish()
      avatar = (
        await open_url(
          normalize_url(session.scene.avatar, bot),
          process=lambda im: ImageOps.fit(im, (64, 64), get_scale_resample()),
        )
        if session.scene.avatar
        else None
      )

      def make() -> ImageSeg:
        chart = BarChart([Item(count, name=match) for match, count in result])
        chart.title = (
          f"{session.scene.name}\n{start_date:%Y-%m-%d %H:%M:%S} 到 "
          f"{end_date:%Y-%m-%d %H:%M:%S} 的{counter.name}内容排行"
        )
        chart.integral_splits = True
        chart.pattern = (
          material_pattern_stripe_from_icon(avatar) if avatar else DEFAULT_STRIPE_PATTERN
        )
        return to_segment(chart.render())

      await UniMessage(await run_sync(make)).send()

    matcher = (
      CommandBuilder()
      .node(f"regex_counter.{counter.id}.match_rank.group")
      .parser(
        Alconna(
          f"群{counter.name}内容排行",
          Args["start?", str, None],
          Args["end?", str, None],
          meta=CommandMeta(f"群内总{counter.name}次数按内容排行", usage=DATE_ARGS_USAGE),
        ),
      )
      .state({"counter": counter})
      .build()
    )
    matcher.handle()(handle_match_rank_group)
    yield matcher

    async def handle_match_rank_user(
      start: str | None,
      end: str | None,
      event: Event,
      session: Uninfo,
      scene_id: SceneId,
      state: T_State,
      sql: async_scoped_session,
      bot: Bot,
    ) -> None:
      counter: Counter = state["counter"]
      user_id = event.get_user_id()
      start_date, end_date = parse_date_range(start, end)
      result = await sql.execute(
        select(Counted.match, count := func.count(Counted.match))
        .where(
          Counted.scene_id == scene_id,
          Counted.user_id == user_id,
          Counted.counter_id == counter.id,
          Counted.time >= start_date,
          Counted.time <= end_date,
        )
        .group_by(Counted.match)
        .order_by(count.desc())
        .limit(20),
      )
      end_date -= timedelta(seconds=1)
      if not result:
        await UniMessage(
          f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 内没有数据",
        ).finish()
      avatar = (
        await open_url(
          normalize_url(session.user.avatar, bot),
          process=lambda im: ImageOps.fit(im, (64, 64), get_scale_resample()),
        )
        if session.user.avatar
        else None
      )
      if session.member and session.member.nick:
        member_name = session.member.nick
      else:
        member_name = session.user.nick or session.user.name or session.user.id

      def make() -> ImageSeg:
        chart = BarChart([Item(count, name=match) for match, count in result])
        chart.title = (
          f"{member_name} 在 {session.scene.name} 内\n{start_date:%Y-%m-%d %H:%M:%S} 到 "
          f"{end_date:%Y-%m-%d %H:%M:%S} 的{counter.name}内容排行"
        )
        chart.integral_splits = True
        chart.pattern = (
          material_pattern_stripe_from_icon(avatar) if avatar else DEFAULT_STRIPE_PATTERN
        )
        return to_segment(chart.render())

      await UniMessage(await run_sync(make)).send()

    matcher = (
      CommandBuilder()
      .node(f"regex_counter.{counter.id}.match_rank.user")
      .parser(
        Alconna(
          f"个人{counter.name}内容排行",
          Args["start?", str, None],
          Args["end?", str, None],
          meta=CommandMeta(f"个人{counter.name}次数按内容排行", usage=DATE_ARGS_USAGE),
        ),
      )
      .state({"counter": counter})
      .build()
    )
    matcher.handle()(handle_match_rank_user)
    yield matcher
