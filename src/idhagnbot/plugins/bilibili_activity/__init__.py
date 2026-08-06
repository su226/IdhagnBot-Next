from collections import deque
from collections.abc import AsyncGenerator

from arclet import letoderea
from arclet.alconna import Alconna, Args, CommandMeta
from arclet.entari import MessageChain, Plugin, Ready, Session, Text, command
from entari_plugin_permission import (
    AUTH_3,
    Permission,
    require_permission,
    system,
)  # entari: plugin
from loguru import logger
from satori.element import escape
from satori.exception import ActionFailed

from idhagnbot.asyncio import create_background_task, delayed_loop, gather_seq
from idhagnbot.permission import ADMIN
from idhagnbot.plugins.bilibili_activity.common import CONFIG, User
from idhagnbot.plugins.bilibili_activity.contents import (
    IgnoredException,
    format_activity,
)
from idhagnbot.plugins.error_report import send_error
from idhagnbot.plugins.redirect import ChannelId
from idhagnbot.support import get_bot_on
from idhagnbot.third_party.bilibili_activity import Activity, fetch, get
from idhagnbot.third_party.bilibili_auth import ApiError

queue: deque[User] = deque()
PLUGIN = Plugin.current()


@letoderea.on(Ready)
async def on_ready() -> None:
    global queue
    queue = deque[User]()
    for user in CONFIG.users:
        queue.append(user)
    PLUGIN.collect(delayed_loop(CONFIG.interval)(try_check_all))


async def new_activities(user: User) -> AsyncGenerator[Activity[object, object]]:
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


async def try_check(user: User) -> int:
    async def try_send(
        activity: Activity[object, object],
        message: MessageChain,
        target: str,
    ) -> None:
        platform, channel_id = target.split(":", maxsplit=1)
        bot = get_bot_on(platform)
        if bot is None:
            logger.warning("没有机器人可以推送动态！")
            return
        try:
            await bot.send_message(channel_id, message)
        except ActionFailed as e:
            description = (
                f"推送 {user._name}({user.uid}) 的动态 {activity.id} 到目标 "
                f"{target} 失败！"
            )
            logger.exception(f"{description}\n动态内容: {activity}")
            create_background_task(send_error("bilibili_activity", description, e))
            try:
                await bot.send_message(
                    channel_id,
                    escape(
                        f"{user._name} 更新了一条动态，但在推送时发送消息失败。\n"
                        f"https://t.bilibili.com/{activity.id}",
                    ),
                )
            except ActionFailed:
                pass

    async def try_send_all(activity: Activity[object, object]) -> None:
        logger.info(f"推送 {user._name}({user.uid}) 的动态 {activity.id}")
        try:
            message = await format_activity(activity)
        except IgnoredException as e:
            logger.info(f"已忽略 {user._name}({user.uid}) 的动态 {activity.id}: {e}")
            return
        except Exception as e:
            description = f"格式化 {user._name}({user.uid}) 的动态 {activity.id} 失败！"
            logger.exception(f"{description}\n动态内容: {activity}")
            create_background_task(send_error("bilibili_activity", description, e))
            message = MessageChain(
                Text(
                    f"{user._name} 更新了一条动态，但在推送时格式化消息失败。\n"
                    f"https://t.bilibili.com/{activity.id}",
                ),
            )
        await gather_seq(try_send(activity, message, target) for target in user.targets)

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
            logger.success(
                f"初始化 {user._name}({user.uid}) 的动态推送完成 {user._offset}",
            )
        except Exception as e:
            description = f"初始化 {user.uid} 的动态推送失败"
            logger.exception(description)
            create_background_task(send_error("bilibili_activity", description, e))
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
        description = f"检查 {user._name}({user.uid}) 的动态更新失败"
        logger.exception(description)
        create_background_task(send_error("bilibili_activity", description, e))
        return 0


async def try_check_all(concurrency: int | None = None) -> tuple[int, int]:
    if concurrency is None:
        concurrency = CONFIG.concurrency
    current_queue = queue
    if concurrency == 0:
        users = list(current_queue)
        current_queue.clear()
    else:
        users = list[User]()
        while current_queue and len(users) < concurrency:
            users.append(current_queue.popleft())
    results = await gather_seq(try_check(user) for user in users)
    current_queue.extend(users)
    return len([x for x in results if x]), sum(results)


@command.on(
    Alconna(
        "推送动态",
        Args["activity_id", int],
        meta=CommandMeta(
            "强制推送B站动态",
            usage="""\
/推送动态 <动态号>
动态的动态号是t.bilibili.com后面的数字
视频的动态号只能通过API获取（不是AV或BV号）""",
        ),
    ),
)
@letoderea.propagate(
    require_permission(
        "idhagnbot.bilibili_activity.force_push",
        default_available=False,
        prompt=True,
    ),
)
async def handle_force_push(
    *,
    session: Session,
    activity_id: int,
    platform_channel_id: ChannelId,
) -> str | MessageChain:
    try:
        src = await get(activity_id)
    except ApiError:
        return "无法获取这条动态"
    activity = Activity.parse(src)
    message = await format_activity(activity, can_ignore=False)
    platform, channel_id = platform_channel_id
    if platform != session.account.platform or channel_id != session.channel.id:
        bot = get_bot_on(platform)
        if bot is None:
            return "目标平台上没有机器人"
        await bot.send_message(channel_id, message)
        channel_name = "未知"
        channel = await bot.channel_get(channel_id)
        if channel is not None:
            channel_name = channel.name or channel_name
        return f"已推送到 {channel_name}"
    return message


system.pre_assign(
    AUTH_3,
    "idhagnbot.bilibili_activity.force_push",
    Permission.VISIT | Permission.AVAILABLE,
)
system.pre_assign(
    ADMIN,
    "idhagnbot.bilibili_activity.force_push",
    Permission.VISIT | Permission.AVAILABLE,
)


@command.on(Alconna("检查动态", meta=CommandMeta("立即检查B站动态更新")))
@letoderea.propagate(
    require_permission(
        "idhagnbot.bilibili_activity.check_now",
        default_available=False,
        prompt=True,
    ),
)
async def handle_check_now() -> str:
    users, activities = await try_check_all(0)
    if users:
        return f"检查动态更新完成，推送了 {users} 个 UP 主的 {activities} 条动态。"
    return "检查动态更新完成，没有可推送的内容。"


system.pre_assign(
    AUTH_3,
    "idhagnbot.bilibili_activity.check_now",
    Permission.VISIT | Permission.AVAILABLE,
)
system.pre_assign(
    ADMIN,
    "idhagnbot.bilibili_activity.check_now",
    Permission.VISIT | Permission.AVAILABLE,
)
