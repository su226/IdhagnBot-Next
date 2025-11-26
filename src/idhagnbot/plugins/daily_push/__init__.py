from datetime import datetime, time, timedelta
from itertools import chain

import nonebot
from apscheduler.job import Job
from nonebot import logger
from nonebot.adapters import Bot
from nonebot.exception import ActionFailed
from pydantic import BaseModel, Field

from idhagnbot.asyncio import create_background_task, gather_map, gather_seq
from idhagnbot.command import CommandBuilder
from idhagnbot.config import SharedConfig, SharedData
from idhagnbot.context import get_target_id
from idhagnbot.permission import CHANNEL_TYPES
from idhagnbot.plugins.daily_push.module import (
  MODULE_REGISTRY,
  SimpleModule,
  TargetAwareModule,
  register,
)
from idhagnbot.plugins.daily_push.modules.constant import ConstantModule
from idhagnbot.plugins.daily_push.modules.countdown import CountdownModule
from idhagnbot.target import TargetConfig, TargetType

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_apscheduler")
nonebot.require("nonebot_plugin_uninfo")
nonebot.require("idhagnbot.plugins.error")
from nonebot_plugin_alconna import (
  Alconna,
  CommandMeta,
  CustomNode,
  Reference,
  Segment,
  Target,
  Text,
  UniMessage,
  get_target,
)
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import SceneType, Uninfo, get_interface

from idhagnbot.plugins.error import send_error


class ModuleConfig(BaseModel, extra="allow"):
  type: str

  def to_module(self) -> SimpleModule | TargetAwareModule:
    return MODULE_REGISTRY[self.type].model_validate(self.model_extra)


class Push(BaseModel):
  time: time
  modules: list[ModuleConfig | list[ModuleConfig]]
  targets: list[TargetConfig]


class Config(BaseModel):
  pushes: dict[str, Push] = Field(default_factory=dict)
  grace_time: timedelta = timedelta(minutes=10)


class Data(BaseModel):
  last_check: dict[str, datetime] = Field(default_factory=dict)


CONFIG = SharedConfig("daily_push", Config, "eager")
DATA = SharedData("daily_push", Data)
driver = nonebot.get_driver()
jobs: list[Job] = []
register("constant")(ConstantModule)
register("countdown")(CountdownModule)
try:
  from idhagnbot.plugins.daily_push.modules.rank import RankModule
except ImportError:
  pass
else:
  register("rank")(RankModule)


@CONFIG.onload()
def _(prev: Config | None, curr: Config) -> None:  # noqa: ARG001
  for job in jobs:
    job.remove()
  jobs.clear()
  grace_time = int(curr.grace_time.total_seconds())
  for push_id, push_config in curr.pushes.items():
    jobs.append(
      scheduler.add_job(
        check_push,
        "cron",
        (push_id,),
        hour=push_config.time.hour,
        minute=push_config.time.minute,
        second=push_config.time.second,
        misfire_grace_time=grace_time,
        coalesce=True,
      ),
    )
    create_background_task(check_push(push_id))


@driver.on_startup
async def _() -> None:
  CONFIG()


async def check_push(push_id: str) -> None:
  config = CONFIG()
  data = DATA()
  push = config.pushes[push_id]
  now = datetime.now()
  send_datetime = datetime.combine(now, push.time)
  if send_datetime > now:
    send_datetime -= timedelta(1)
  if send_datetime <= data.last_check.get(push_id, datetime.min):
    return
  if now > send_datetime + config.grace_time:
    logger.warning(f"超过最大发送时间，将不会发送每日推送 {push_id}")
  else:
    logger.info(f"发送每日推送 {push_id}")
    await send_push(push)
  data.last_check[push_id] = now
  DATA.dump()


async def format_one_target_aware(
  module: TargetAwareModule,
  config: ModuleConfig,
  target: Target,
) -> list[UniMessage[Segment]]:
  try:
    return await module.format(target)
  except Exception as e:
    logger.exception(f"每日推送模块运行失败: {config}")
    description = f"模块运行失败：{config.type}"
    create_background_task(send_error("daily_push", description, e))
    return [UniMessage(Text(description))]


async def format_one(
  config: ModuleConfig,
  targets: list[Target],
) -> dict[Target, list[UniMessage[Segment]]]:
  module = config.to_module()
  if isinstance(module, TargetAwareModule):
    return await gather_map(
      {target: format_one_target_aware(module, config, target) for target in targets},
    )
  try:
    messages = await module.format()
  except Exception as e:
    logger.exception(f"每日推送模块运行失败: {config}")
    description = f"模块运行失败：{config.type}"
    create_background_task(send_error("daily_push", description, e))
    messages = [UniMessage[Segment](Text(description))]
  return dict.fromkeys(targets, messages)


async def format_forward(
  modules: list[ModuleConfig],
  targets: list[Target],
) -> dict[Target, list[UniMessage[Segment]]]:
  merged = {target: list[UniMessage[Segment]]() for target in targets}
  for one in await gather_seq(format_one(module, targets) for module in modules):
    for target, messages in one.items():
      merged[target].extend(messages)
  return {
    target: [UniMessage(Reference(nodes=[CustomNode("", "", message) for message in messages]))]
    if messages
    else []
    for target, messages in merged.items()
  }


async def format_all(
  modules: list[ModuleConfig | list[ModuleConfig]],
  targets: list[Target],
) -> dict[Target, list[UniMessage[Segment]]]:
  merged = {target: list[UniMessage[Segment]]() for target in targets}
  for one in await gather_seq(
    format_forward(module, targets) if isinstance(module, list) else format_one(module, targets)
    for module in modules
  ):
    for target, messages in one.items():
      merged[target].extend(messages)
  return merged


async def get_bot_name(bot: Bot, target: Target) -> str:
  interface = get_interface(bot)
  if not interface:
    return "IdhagnBot"
  if target.channel:
    member = await interface.get_member(SceneType.GUILD, target.parent_id, bot.self_id)
  elif target.private:
    member = await interface.get_member(SceneType.PRIVATE, target.id, bot.self_id)
  else:
    member = await interface.get_member(SceneType.GROUP, target.id, bot.self_id)
  if member:
    return member.nick or member.user.nick or member.user.name or "IdhagnBot"
  if user := await interface.get_user(bot.self_id):
    return user.nick or user.name or "IdhagnBot"
  return "IdhagnBot"


async def init_reference(target: Target, messages: list[UniMessage[Segment]]) -> None:
  if any(isinstance(message[0], Reference) for message in messages):
    bot = await target.select()
    bot_name = await get_bot_name(bot, target)
    for message in messages:
      if isinstance(message[0], Reference):
        for node in message[0].children:
          if isinstance(node, CustomNode):
            node.uid = bot.self_id
            node.name = bot_name


async def send_one(target: Target, messages: list[UniMessage[Segment]]) -> None:
  await init_reference(target, messages)
  failed = False
  for message in messages:
    try:
      await message.send(target)
    except ActionFailed as e:
      target_id = await get_target_id(target)
      description = f"推送到目标 {target_id} 失败"
      logger.exception(f"{description}: {message}")
      create_background_task(send_error("daily_push", description, e))
      failed = True
  if failed:
    try:
      await UniMessage(Text("发送部分每日推送失败，可运行 /今天 重新查看")).send(target)
    except ActionFailed:
      pass


async def send_push(push: Push) -> None:
  targets = [target.target for target in push.targets]
  messages = await format_all(push.modules, targets)
  await gather_seq(send_one(target, messages[target]) for target in targets)


resend_push = (
  CommandBuilder()
  .node("daily_push")
  .parser(Alconna("每日推送", meta=CommandMeta("重新发送每日推送")))
  .build()
)


async def target_match(target: TargetConfig, session: Uninfo) -> bool:
  bot = await target.target.select()
  if bot.self_id != session.self_id:
    return False
  parent_id = session.scene.parent.id if session.scene.parent else ""
  if session.scene.id != target.id or parent_id != target.parent_id:
    return False
  if target.type == TargetType.PRIVATE:
    return session.scene.type == SceneType.PRIVATE
  if target.type == TargetType.GROUP:
    return session.scene.type == SceneType.GROUP
  return session.scene.type in CHANNEL_TYPES


async def format_if_match(push: Push, session: Uninfo) -> list[UniMessage[Segment]]:
  matches = await gather_seq(target_match(target, session) for target in push.targets)
  targets = [target.target for target, match in zip(push.targets, matches, strict=True) if match]
  if targets:
    formatted = await format_all(push.modules, [targets[0]])
    return formatted[targets[0]]
  return []


@resend_push.handle()
async def handle_resend_push(*, session: Uninfo) -> None:
  messages = list(
    chain.from_iterable(
      await gather_seq(format_if_match(push, session) for push in CONFIG().pushes.values()),
    ),
  )
  await init_reference(get_target(), messages)
  if not messages:
    if session.scene.type in CHANNEL_TYPES:
      await UniMessage(Text("当前会话没有每日推送（请检查是否在正确的子频道）")).send()
    else:
      await UniMessage(Text("当前会话没有每日推送")).send()
  for message in messages:
    await message.send()
