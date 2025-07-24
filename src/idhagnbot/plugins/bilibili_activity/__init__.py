import asyncio
from collections import deque
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Optional

import nonebot
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_MISSED, JobEvent
from loguru import logger
from nonebot.exception import ActionFailed

from idhagnbot.command import CommandBuilder
from idhagnbot.context import SceneId, SceneIdRaw, to_scene, to_target
from idhagnbot.permission import ADMINISTRATOR_OR_ABOVE
from idhagnbot.plugins.bilibili_activity import common, contents
from idhagnbot.target import TargetConfig
from idhagnbot.third_party.bilibili_activity import Activity, fetch, get

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_apscheduler")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, Match
from nonebot_plugin_alconna.uniseg import Segment, Text, UniMessage
from nonebot_plugin_apscheduler import scheduler

driver = nonebot.get_driver()
queue = deque[common.User]()


@common.CONFIG.onload()
def onload(prev: Optional[common.Config], curr: common.Config) -> None:
  global queue
  queue = deque[common.User]()
  for i in curr.users:
    queue.append(i)
  delta = timedelta(seconds=curr.interval)
  schedule(datetime.now() + delta)


def schedule(date: datetime) -> None:
  async def check_activity() -> None:
    try:
      await try_check_all()
    except asyncio.CancelledError:
      pass  # 这里仅仅是防止在关闭机器人时日志出现 CancelledError

  scheduler.add_job(
    check_activity,
    "date",
    id="bilibili_activity",
    replace_existing=True,
    run_date=date,
  )


def schedule_next(event: JobEvent) -> None:
  if event.job_id == "bilibili_activity":
    schedule(datetime.now() + timedelta(seconds=common.CONFIG().interval))


scheduler.add_listener(schedule_next, EVENT_JOB_EXECUTED | EVENT_JOB_MISSED)


@driver.on_bot_connect
async def on_bot_connect() -> None:
  common.CONFIG()


async def new_activities(
  user: common.User,
) -> AsyncGenerator[Activity[object, object], None]:
  offset = ""
  while offset is not None:
    raw, next_offset = await fetch(user.uid, offset)
    activities = [Activity.parse(x) for x in raw]
    for activity in activities:
      user._name = activity.name
      if not user._offset or activity.id > user._offset:
        yield activity
      elif not activity.top:
        return
    offset = next_offset


async def send_error(message: str, e: Exception) -> None:
  config = common.CONFIG()
  data = common.DATA()
  now = datetime.now(timezone.utc)
  if now < data.last_warn + config.warn_interval:
    return
  data.last_warn = now
  common.DATA.dump()
  message_send = UniMessage(Text(f"{message}\n{e!r}"))
  await asyncio.gather(*[message_send.send(target.target) for target in config.warn_target])


async def try_check(user: common.User) -> int:
  async def try_send(
    activity: Activity[object, object],
    message: UniMessage[Segment],
    target: TargetConfig,
  ) -> None:
    try:
      await message.send(target.target)
    except ActionFailed:
      logger.exception(
        f"推送 {user._name}({user.uid}) 的动态 {activity.id} 到目标 {target} 失败！\n"
        f"动态内容: {activity}",
      )
      try:
        await UniMessage(
          Text(
            f"{user._name} 更新了一条动态，但在推送时发送消息失败。"
            f"https://t.bilibili.com/{activity.id}",
          ),
        ).send(target.target)
      except ActionFailed:
        pass

  async def try_send_all(activity: Activity[object, object]) -> None:
    logger.info(f"推送 {user._name}({user.uid}) 的动态 {activity.id}")
    try:
      message = await contents.format(activity)
    except common.IgnoredException as e:
      logger.info(f"已忽略 {user._name}({user.uid}) 的动态 {activity.id}: {e}")
      return
    except Exception:
      logger.exception(
        f"格式化 {user._name}({user.uid}) 的动态 {activity.id} 失败！\n动态内容: {activity}",
      )
      message = UniMessage[Segment](
        Text(
          f"{user._name} 更新了一条动态，但在推送时格式化消息失败。"
          f"https://t.bilibili.com/{activity.id}",
        ),
      )
    await asyncio.gather(*[try_send(activity, message, target) for target in user.targets])

  if user._offset == -1:
    try:
      raw, _ = await fetch(user.uid)
      activities = [Activity.parse(x) for x in raw]
      if len(activities) > 1:
        user._offset = max(activities[0].id, activities[1].id)
      elif activities:
        user._offset = activities[0].id
      else:
        user._offset = 0
      if activities:
        user._name = activities[0].name
      logger.success(f"初始化 {user._name}({user.uid}) 的动态推送完成 {user._offset}")
    except Exception as e:
      message = f"初始化 {user.uid} 的动态推送失败"
      logger.exception(message)
      await send_error(message, e)
    return 0

  try:
    activities = list[Activity[object, object]]()
    async for activity in new_activities(user):
      activities.append(activity)
    activities.reverse()
    for activity in activities:
      user._offset = activity.id
      await try_send_all(activity)
    logger.debug(f"检查 {user._name}({user.uid}) 的动态更新完成")
    return len(activities)
  except Exception as e:
    message = f"检查 {user._name}({user.uid}) 的动态更新失败"
    logger.exception(message)
    await send_error(message, e)
    return 0


async def try_check_all(concurrency: Optional[int] = None) -> tuple[int, int]:
  if concurrency is None:
    concurrency = common.CONFIG().concurrency
  current_queue = queue
  if concurrency == 0:
    users = list(current_queue)
    current_queue.clear()
  else:
    users = list[common.User]()
    while current_queue and len(users) < concurrency:
      users.append(current_queue.popleft())
  results = await asyncio.gather(*[try_check(user) for user in users])
  current_queue.extend(users)
  return len([x for x in results if x]), sum(results)


force_push = (
  CommandBuilder()
  .node("bilibili_activity.force_push")
  .parser(
    Alconna(
      "推送动态",
      Args["id", int],
      meta=CommandMeta(
        "强制推送B站动态",
        usage="""\
/推送动态 <动态号>
动态的动态号是t.bilibili.com后面的数字
视频的动态号只能通过API获取（不是AV或BV号）""",
      ),
    ),
  )
  .default_grant_to(ADMINISTRATOR_OR_ABOVE)
  .build()
)


@force_push.handle()
async def handle_force_push(id: Match[int], scene_id: SceneId, scene_id_raw: SceneIdRaw) -> None:
  try:
    src = await get(id.result)
  except Exception:
    await force_push.finish("无法获取这条动态")
  activity = Activity.parse(src)
  message = await contents.format(activity, False)
  if scene_id != scene_id_raw:
    target = to_target(scene_id)
    await message.send(target)
    scene = await to_scene(scene_id)
    name = scene.name or "未知" if scene else "未知"
    await UniMessage(Text(f"已推送到 {name}")).send()
  else:
    await message.send()


check_now = (
  CommandBuilder()
  .node("bilibili_activity.check_now")
  .parser(Alconna("检查动态", meta=CommandMeta("立即检查B站动态更新")))
  .default_grant_to(ADMINISTRATOR_OR_ABOVE)
  .build()
)


@check_now.handle()
async def handle_check_now() -> None:
  users, activities = await try_check_all(0)
  if users:
    await check_now.finish(f"检查动态更新完成，推送了 {users} 个 UP 主的 {activities} 条动态。")
  else:
    await check_now.finish("检查动态更新完成，没有可推送的内容。")
