import re
from collections.abc import Generator
from datetime import datetime, timedelta
from typing import Any, ClassVar

import nonebot
from nonebot.adapters import Event
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.command import COMMAND_LIKE_KEY, IDHAGNBOT_KEY, CommandBuilder
from idhagnbot.config import SharedConfig
from idhagnbot.context import SceneId, SceneIdRaw, get_scene
from idhagnbot.datetime import DATE_ARGS_USAGE, parse_date_range
from idhagnbot.message import EventTime, UniMsg

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, UniMessage
from nonebot_plugin_orm import Model, async_scoped_session
from nonebot_plugin_uninfo import Interface, QryItrface, SceneType


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
  __tablename__: ClassVar[Any] = "idhagnbot_regex_counter_counted"
  id: Mapped[int] = mapped_column(primary_key=True)
  time: Mapped[datetime]
  scene_id: Mapped[str]
  counter_id: Mapped[str]
  user_id: Mapped[str]
  match: Mapped[str]


CONFIG = SharedConfig("regex_counter", Config, "eager")
matchers = list[type[Matcher]]()
driver = nonebot.get_driver()


@driver.on_startup
async def _() -> None:
  CONFIG()


@CONFIG.onload()
def _(prev: Config | None, curr: Config) -> None:
  for matcher in matchers:
    matcher.destroy()
  matchers.clear()
  for counter in curr.counters:
    matchers.extend(register(counter))


async def get_member_name(
  interface: Interface,
  scene_type: SceneType,
  scene_id: str,
  user_id: str,
) -> str:
  if member := await interface.get_member(scene_type, scene_id, user_id):
    return member.nick or member.user.nick or member.user.name or member.user.id
  if user := await interface.get_user(user_id):
    return user.nick or user.name or user.id
  return user_id


def register(counter: Counter) -> Generator[type[Matcher], None, None]:
  async def check_count(event: Event, message: UniMsg, state: T_State) -> bool:
    try:
      event.get_user_id()
    except (ValueError, NotImplementedError):
      return False
    if state[IDHAGNBOT_KEY][COMMAND_LIKE_KEY]:
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
    scene = await get_scene(scene_id)
    if not scene:
      raise ValueError("获取群信息失败")
    await UniMessage(
      f"{scene.name} 内 {start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} "
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
    scene_id: SceneId,
    state: T_State,
    interface: QryItrface,
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
    scene = await get_scene(scene_id)
    if not scene:
      raise ValueError("获取群信息失败")
    member_name = await get_member_name(interface, scene.type, scene.id, user_id)
    await UniMessage(
      f"{member_name} 在 {scene.name} 内 {start_date:%Y-%m-%d %H:%M:%S} 到 "
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
      .limit(10),
    )
    scene = await get_scene(scene_id)
    if not scene:
      raise ValueError("获取群信息失败")
    lines = [
      f"{scene.name} 内 {start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} "
      f"的{counter.name}次数排行",
    ]
    for rank, (user_id, count) in enumerate(result, 1):
      member_name = await get_member_name(interface, scene.type, scene.id, user_id)
      lines.append(f"{rank}. {member_name} × {count} 条")
    await UniMessage("\n".join(lines)).send()

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
      scene_id: SceneId,
      state: T_State,
      sql: async_scoped_session,
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
        .limit(10),
      )
      scene = await get_scene(scene_id)
      if not scene:
        raise ValueError("获取群信息失败")
      lines = [f"{scene.name} 内的{counter.name}内容排行"]
      for rank, (match, count) in enumerate(result, 1):
        lines.append(f"{rank}. {match} × {count} 条")
      await UniMessage("\n".join(lines)).send()

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
      scene_id: SceneId,
      state: T_State,
      interface: QryItrface,
      sql: async_scoped_session,
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
        .limit(10),
      )
      scene = await get_scene(scene_id)
      if not scene:
        raise ValueError("获取群信息失败")
      member_name = await get_member_name(interface, scene.type, scene.id, user_id)
      lines = [
        f"{member_name} 在 {scene.name} 内 {start_date:%Y-%m-%d %H:%M:%S} 到 "
        f"{end_date:%Y-%m-%d %H:%M:%S} 的{counter.name}内容排行",
      ]
      for rank, (match, count) in enumerate(result, 1):
        lines.append(f"{rank}. {match} × {count} 条")
      await UniMessage("\n".join(lines)).send()

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
