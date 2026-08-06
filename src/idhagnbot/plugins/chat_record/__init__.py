from datetime import datetime, timedelta
from functools import cached_property

import nonebot
from nonebot.adapters import Bot
from nonebot.consts import PREFIX_KEY, RAW_CMD_KEY
from nonebot.matcher import Matcher, current_event
from nonebot.message import event_preprocessor, run_preprocessor
from nonebot.rule import CommandRule, Rule, ShellCommandRule
from nonebot.typing import T_State
from sqlalchemy import func, select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.context import MaybeSceneIdRaw, SceneId, UserId, get_bot_id, get_target_id
from idhagnbot.hook import on_message_sent
from idhagnbot.hook.common import SentMessage
from idhagnbot.message import EventTime, MessageId, OrigUniMsg
from idhagnbot.message.common import MaybeMessageId, message_id
from idhagnbot.webui.dashboard import OverviewNumber, register

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
from nonebot_plugin_alconna import (
  ALCONNA_RESULT,
  AlconnaMatcher,
  CommandResult,
  Segment,
  Target,
  UniMessage,
)
from nonebot_plugin_orm import Model, get_session


class Message(Model):
  __tablename__ = "idhagnbot_chat_record_message"
  record_id: Mapped[int] = mapped_column(primary_key=True)
  time: Mapped[datetime]
  scene_id: Mapped[str]
  user_id: Mapped[str]
  message_id: Mapped[str]
  content: Mapped[str]
  outgoing: Mapped[bool] = mapped_column(server_default="0")
  caused_by: Mapped[str | None]

  @cached_property
  def unimessage(self) -> UniMessage[Segment]:
    return UniMessage.load(self.content)


class MatcherCall(Model):
  __tablename__ = "idhagnbot_chat_record_matcher_call"
  record_id: Mapped[int] = mapped_column(primary_key=True)
  time: Mapped[datetime]
  matcher_type: Mapped[str]
  scene_id: Mapped[str | None]
  message_id: Mapped[str | None]
  plugin_id: Mapped[str | None]
  module_name: Mapped[str | None]
  lineno: Mapped[int | None]
  command_name: Mapped[str | None]
  command_alias: Mapped[str | None]


@event_preprocessor
async def _(
  event_time: EventTime,
  scene_id: SceneId,
  user_id: UserId,
  message_id: MessageId,
  message: OrigUniMsg,
) -> None:
  async with get_session() as sql:
    sql.add(
      Message(
        time=event_time,
        scene_id=scene_id,
        user_id=user_id,
        message_id=message_id,
        content=message.dump(media_save_dir=False, json=True),
        outgoing=False,
        caused_by=None,
      ),
    )
    await sql.commit()


@on_message_sent
async def _(
  bot: Bot,
  original_message: UniMessage[Segment],
  messages: list[SentMessage],
  target: Target,
) -> None:
  self_id = await get_bot_id(bot)
  scene_id = await get_target_id(target)
  event = current_event.get(None)
  caused_by = await message_id(bot, event) if event else None
  async with get_session() as sql:
    for message in messages:
      sql.add(
        Message(
          time=message.time,
          scene_id=scene_id,
          user_id=self_id,
          message_id=message.id,
          content=message.content.dump(media_save_dir=False, json=True),
          outgoing=True,
          caused_by=caused_by,
        ),
      )
    await sql.commit()


def extract_command_name_from_rule(rule: Rule) -> str:
  for checker in rule.checkers:
    if isinstance(checker.call, (CommandRule, ShellCommandRule)):
      sep = next(iter(nonebot.get_driver().config.command_sep))
      return sep.join(checker.call.cmds[0])
  raise ValueError("无法提取命令名")


@run_preprocessor
async def _(
  matcher: Matcher,
  state: T_State,
  scene_id: MaybeSceneIdRaw,
  message_id: MaybeMessageId,
  event_time: EventTime,
) -> None:
  # on_alconna 的 type 为空字符串
  matcher_type = "alconna" if isinstance(matcher, AlconnaMatcher) else matcher.type
  if source := matcher._source:
    plugin_id = source.plugin_id
    module_name = source.module_name
    lineno = source.lineno
  else:
    plugin_id = None
    module_name = None
    lineno = None
  result: CommandResult | None = state.get(ALCONNA_RESULT)
  if result:
    command_name = result.source.name
    command_alias = result.result.header_match.origin
  elif raw_cmd := state[PREFIX_KEY][RAW_CMD_KEY]:
    command_name = extract_command_name_from_rule(matcher.rule)
    command_alias = raw_cmd
  else:
    command_name = None
    command_alias = None
  async with get_session() as sql:
    sql.add(
      MatcherCall(
        time=event_time,
        matcher_type=matcher_type,
        scene_id=scene_id,
        message_id=message_id,
        plugin_id=plugin_id,
        module_name=module_name,
        lineno=lineno,
        command_name=command_name,
        command_alias=command_alias,
      ),
    )
    await sql.commit()


@register("chat_record:message_incoming")
async def get_message_incoming() -> OverviewNumber:
  time_now = datetime.now()
  time_start = time_now - timedelta(1)
  async with get_session() as sql:
    result = await sql.execute(
      select(func.count())
      .select_from(Message)
      .where(Message.time >= time_start, Message.time <= time_now, ~Message.outgoing),
    )
    count = result.scalar_one()
  return OverviewNumber(name="24h 收到消息", icon="message", type="number", value=count)


@register("chat_record:message_outgoing")
async def get_message_outgoing() -> OverviewNumber:
  time_now = datetime.now()
  time_start = time_now - timedelta(1)
  async with get_session() as sql:
    result = await sql.execute(
      select(func.count())
      .select_from(Message)
      .where(Message.time >= time_start, Message.time <= time_now, Message.outgoing),
    )
    count = result.scalar_one()
  return OverviewNumber(name="24h 发出消息", icon="message", type="number", value=count)
