import asyncio
from copy import deepcopy
from datetime import datetime, time, timedelta
from itertools import chain
from typing import Optional, Union

import nonebot
from apscheduler.job import Job
from nonebot import logger
from nonebot.adapters import Bot
from nonebot.exception import ActionFailed
from pydantic import BaseModel, Field

from idhagnbot.command import CommandBuilder
from idhagnbot.config import SharedConfig, SharedData
from idhagnbot.permission import CHANNEL_TYPES
from idhagnbot.plugins.daily_push.module import MODULE_REGISTRY, ModuleConfig, register
from idhagnbot.plugins.daily_push.modules.constant import ConstantModuleConfig
from idhagnbot.target import TargetConfig, TargetType

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_apscheduler")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, CommandMeta
from nonebot_plugin_alconna.uniseg import CustomNode, Reference, Segment, Target, Text, UniMessage
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import SceneType, Uninfo, get_interface


class PushModule(BaseModel, extra="allow"):
  type: str

  def to_module_config(self) -> ModuleConfig:
    return MODULE_REGISTRY[self.type].model_validate(self.model_extra)


class Push(BaseModel):
  time: time
  modules: list[Union[PushModule, list[PushModule]]]
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
register("constant")(ConstantModuleConfig)


@CONFIG.onload()
def _(prev: Optional[Config], curr: Config) -> None:  # noqa: ARG001
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
    asyncio.create_task(check_push(push_id))


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


async def format_one(module: PushModule) -> list[UniMessage[Segment]]:
  try:
    return await module.to_module_config().create_module().format()
  except Exception:
    logger.exception(f"每日推送模块运行失败: {module}")
    return [UniMessage(Text(f"模块运行失败：{module.type}"))]


async def format_forward(modules: list[PushModule]) -> list[UniMessage[Segment]]:
  nodes = [
    CustomNode("", "", message)
    for message in chain.from_iterable(
      await asyncio.gather(*(format_one(module) for module in modules)),
    )
  ]
  if not nodes:
    return []
  return [UniMessage(Reference(nodes=nodes))]


async def format_all(push: Push) -> list[UniMessage[Segment]]:
  return list(
    chain.from_iterable(
      i
      for i in await asyncio.gather(
        *(
          format_forward(module) if isinstance(module, list) else format_one(module)
          for module in push.modules
        ),
      )
    ),
  )


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


async def send_one(target: Target, messages: list[UniMessage[Segment]]) -> None:
  if any(isinstance(message[0], Reference) for message in messages):
    bot = await target.select()
    bot_name = await get_bot_name(bot, target)
    messages = deepcopy(messages)
    for message in messages:
      if isinstance(message[0], Reference):
        for node in message[0].children:
          if isinstance(node, CustomNode):
            node.uid = bot.self_id
            node.name = bot_name
  failed = False
  for message in messages:
    try:
      await message.send(target)
    except ActionFailed:
      logger.exception(f"发送部分每日推送到目标 {target} 失败: {message}")
      failed = True
  if failed:
    try:
      await UniMessage(Text("发送部分每日推送失败，可运行 /今天 重新查看")).send(target)
    except ActionFailed:
      pass


async def send_push(push: Push) -> None:
  messages = await format_all(push)
  await asyncio.gather(*(send_one(target.target, messages) for target in push.targets))


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
  return (
    await format_all(push)
    if any(await asyncio.gather(*(target_match(target, session) for target in push.targets)))
    else []
  )


@resend_push.handle()
async def handle_resend_push(session: Uninfo) -> None:
  messages = list(chain.from_iterable(
    await asyncio.gather(*(format_if_match(push, session) for push in CONFIG().pushes.values())),
  ))
  if not messages:
    if session.scene.type in CHANNEL_TYPES:
      await UniMessage(Text("当前会话没有每日推送（请检查是否在正确的子频道）")).send()
    else:
      await UniMessage(Text("当前会话没有每日推送")).send()
  for message in messages:
    await message.send()
