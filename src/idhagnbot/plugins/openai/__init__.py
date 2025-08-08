import random
from datetime import datetime, timedelta
from typing import Literal, TypedDict

import nonebot
from arclet.alconna import AllParam
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from pydantic import BaseModel, HttpUrl, SecretStr, TypeAdapter
from sqlalchemy import desc, select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.command import CommandBuilder
from idhagnbot.config import SharedConfig
from idhagnbot.context import SceneIdRaw
from idhagnbot.http import get_session

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import (
  Alconna,
  Args,
  CommandMeta,
  Match,
  Option,
  Text,
  UniMessage,
  store_true,
)
from nonebot_plugin_orm import Model, async_scoped_session
from nonebot_plugin_uninfo import Uninfo


class Config(BaseModel):
  key: SecretStr = SecretStr("")
  server: HttpUrl = HttpUrl("https://api.openai.com/v1")
  model: str = "gpt-4.1"
  system: str = ""
  info: bool = True
  secret: bool = False
  history_time: timedelta = timedelta(1)
  history_limit: int = 100


CONFIG = SharedConfig("openai", Config)


def extract_nickname(session: Uninfo) -> str:
  if session.member and session.member.nick:
    return session.member.nick
  return session.user.nick or session.user.name or session.user.id


class History(Model):
  __tablename__ = "idhagnbot_openai_history"
  id: Mapped[int] = mapped_column(primary_key=True)
  scene: Mapped[str]
  role: Mapped[Literal["user", "assistant"]]
  nickname: Mapped[str]
  superuser: Mapped[bool]
  content: Mapped[str]
  time: Mapped[datetime]
  ignored: Mapped[bool] = mapped_column(server_default="0")


class Ignore(Model):
  __tablename__ = "idhagnbot_openai_ignore"
  scene: Mapped[str] = mapped_column(primary_key=True)
  time: Mapped[datetime]


class ResMessage(TypedDict):
  content: str


class ResChoice(TypedDict):
  message: ResMessage


class ResData(TypedDict):
  created: int
  choices: list[ResChoice]


ResDataAdapter = TypeAdapter(ResData)


class ReqMessage(TypedDict):
  role: Literal["user", "system", "assistant"]
  content: str


class ReqData(TypedDict):
  model: str
  messages: list[ReqMessage]


class ReqHeaders(TypedDict):
  Authorization: str


ai = (
  CommandBuilder()
  .node("openai.ai")
  .parser(
    Alconna(
      "ai",
      Option(
        "--no-context",
        dest="no_context",
        action=store_true,
        default=False,
        help_text="禁用上下文",
      ),
      Args["message", AllParam(str)],
      meta=CommandMeta("AI对话"),
    ),
  )
  .build()
)


@ai.handle()
async def handle_ai(
  bot: Bot,
  event: Event,
  session: Uninfo,
  message: Match[UniMessage[Text]],
  sql: async_scoped_session,
  scene_id: SceneIdRaw,
  no_context: bool,
) -> None:
  config = CONFIG()
  time = datetime.now()
  if no_context:
    history = []
  else:
    ignore_time = await sql.get(Ignore, scene_id)
    min_time = time - config.history_time
    min_time = max(min_time, ignore_time.time) if ignore_time else min_time
    history = list(
      await sql.scalars(
        select(History)
        .where(History.scene == scene_id, History.time > min_time, ~History.ignored)
        .order_by(desc(History.time))
        .limit(config.history_limit),
      ),
    )
  current = History(
    scene=scene_id,
    role="user",
    nickname=extract_nickname(session),
    superuser=await SUPERUSER(bot, event),
    content=message.result.extract_plain_text(),
    time=time,
    ignored=no_context,
  )
  history.append(current)
  secret = random.randint(1000, 9999) if config.secret else 0
  messages: list[ReqMessage] = []
  if config.system:
    messages.append(ReqMessage(role="system", content=config.system.format(secret=secret)))
  for item in history:
    if config.info and item.role == "user":
      secret_info = f"，带有暗号{secret}" if config.secret and item.superuser else ""
      messages.append(
        ReqMessage(
          role="system",
          content=f"下一条消息来自{item.nickname}{secret_info}，"
          f"发送于{item.time:%Y-%m-%d %H:%M:%S}",
        ),
      )
    messages.append(ReqMessage(role=item.role, content=item.content))
  async with get_session().post(
    f"{config.server}/chat/completions",
    headers=ReqHeaders(Authorization=f"Bearer {config.key.get_secret_value()}"),
    json=ReqData(model=config.model, messages=messages),
  ) as response:
    data = ResDataAdapter.validate_python(await response.json())
  content = data["choices"][0]["message"]["content"]
  sql.add(current)
  sql.add(
    History(
      scene=scene_id,
      role="assistant",
      nickname="",
      superuser=False,
      content=content,
      time=datetime.fromtimestamp(data["created"]),
      ignored=no_context,
    ),
  )
  await sql.commit()
  await ai.send(content)


reset = (
  CommandBuilder()
  .node("openai.reset")
  .parser(Alconna("ai重置", meta=CommandMeta("重置AI对话上下文")))
  .build()
)


@reset.handle()
async def handle_reset(scene_id: SceneIdRaw, sql: async_scoped_session) -> None:
  current = await sql.get(Ignore, scene_id)
  if current:
    current.time = datetime.now()
    sql.add(current)
  else:
    sql.add(Ignore(scene=scene_id, time=datetime.now()))
  await sql.commit()
  await reset.finish("已重置上下文")
