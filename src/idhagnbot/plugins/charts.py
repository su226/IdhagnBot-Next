import asyncio
from datetime import datetime, timedelta

from arclet.alconna import Alconna, Args, CommandMeta
from arclet.entari import Account, MessageChain, Session, command
from arclet.entari import Image as ImageSeg
from arclet.entari.command import Match
from arclet.letoderea import propagate
from entari_plugin_database import AsyncSession, select  # entari: plugin
from entari_plugin_permission import require_permission
from PIL import Image, ImageOps
from sqlalchemy import func

from idhagnbot.asyncio import gather_seq
from idhagnbot.datetime import DATE_ARGS_USAGE, parse_date_range
from idhagnbot.image import SCALE_RESAMPLE, open_url, resize_height, to_segment
from idhagnbot.image.bar_chart import (
    DEFAULT_STRIPE_PATTERN,
    BarChart,
    ColumnChart,
    Item,
    material_palette_from_icon,
    material_pattern_stripe_from_icon,
)
from idhagnbot.meme_common import get_member, get_user
from idhagnbot.plugins.record import Channel, Message, MessageRevision, Run


async def open_avatar(url: str | None, account: Account) -> Image.Image | None:
    return await open_url(str(account.ensure_url(url))) if url else None


async def get_name_and_avatar(
    session: Session,
    user_id: str,
) -> tuple[str, Image.Image | None]:
    if member := await get_member(session, user_id):
        name = member.nick or member.user.nick or member.user.name or member.user.id
        return name, await open_avatar(member.user.avatar, session.account)
    if user := await get_user(session, user_id):
        name = user.nick or user.name or user.id
        return name, await open_avatar(user.avatar, session.account)
    return user_id, None


leaderboard = Alconna(
    "leaderboard",
    Args["start?", str, None],
    Args["end?", str, None],
    meta=CommandMeta(
        "查看最近的发言排行",
        usage=DATE_ARGS_USAGE,
        extra={
            "idhagnbot_i18n_names": {
                "leaderboard": "en-US",
                "rank": "en-US",
                "排名": "zh-CN",
                "排行": "zh-CN",
            },
        },
    ),
)
leaderboard.shortcut("rank", command="leaderboard")
leaderboard.shortcut("排名", command="leaderboard")
leaderboard.shortcut("排行", command="leaderboard")


@command.on(leaderboard)
@propagate(require_permission("idhagnbot.charts.leaderboard", prompt=True))
async def handle_leaderboard(
    start: Match[str | None],
    end: Match[str | None],
    session: Session,
    db: AsyncSession,
) -> str | MessageChain:
    start_date, end_date = parse_date_range(start.result, end.result)
    result = await db.execute(
        select(Message.user_id, count := func.count(Message.id))
        .join(
            MessageRevision,
            (Message.platform == MessageRevision.platform)
            & (Message.channel_id == MessageRevision.channel_id)
            & (Message.id == MessageRevision.message_id)
            & (MessageRevision.revision == 1),
        )
        .join(
            Channel,
            (Message.platform == Channel.platform) & (Message.channel_id == Channel.id),
        )
        .where(
            Channel.platform == session.account.platform,
            Channel.guild_id == session.guild.id,
            MessageRevision.created_at >= start_date,
            MessageRevision.created_at <= end_date,
            ~Message.outgoing,
        )
        .group_by(Message.user_id)
        .order_by(count.desc())
        .limit(20),
    )
    result = result.all()
    end_date -= timedelta(seconds=1)  # 显示 23:59:59 而不是 00:00:00，以防误会
    if not result:
        return (
            f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 内没有数据"
        )
    names_and_avatars = await gather_seq(
        get_name_and_avatar(session, user_id) for user_id, _ in result
    )

    def make() -> ImageSeg:
        chart = BarChart()
        chart.title = (
            f"{session.guild.name}\n"
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

    return MessageChain(await asyncio.to_thread(make))


command_leaderboard = Alconna(
    "command_leaderboard",
    Args["start?", str, None],
    Args["end?", str, None],
    meta=CommandMeta(
        "查看最近的命令调用排行",
        usage=DATE_ARGS_USAGE,
        extra={
            "idhagnbot_i18n_names": {
                "command_leaderboard": "en-US",
                "command_rank": "en-US",
                "命令排名": "zh-CN",
                "命令排行": "zh-CN",
            },
        },
    ),
)
command_leaderboard.shortcut("command_rank", command="command_leaderboard")
command_leaderboard.shortcut("命令排名", command="command_leaderboard")
command_leaderboard.shortcut("命令排行", command="command_leaderboard")


@command.on(command_leaderboard)
@propagate(require_permission("idhagnbot.charts.command_leaderboard", prompt=True))
async def handle_command_leaderboard(
    start: Match[str | None],
    end: Match[str | None],
    session: Session,
    db: AsyncSession,
) -> str | MessageChain:
    start_date, end_date = parse_date_range(start.result, end.result)
    result = await db.execute(
        select(Run.command_name, count := func.count(Run.command_name))
        .join(
            Channel,
            (Run.platform == Channel.platform) & (Run.channel_id == Channel.id),
        )
        .where(
            Channel.platform == session.account.platform,
            Channel.guild_id == session.guild.id,
            Run.run_at >= start_date,
            Run.run_at <= end_date,
        )
        .group_by(Run.command_name)
        .having(Run.command_name.isnot(None))
        .order_by(count.desc())
        .limit(20),
    )
    result = result.all()
    end_date -= timedelta(seconds=1)  # 显示 23:59:59 而不是 00:00:00，以防误会
    if not result:
        return (
            f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 内没有数据"
        )
    avatar = (
        await open_url(
            str(session.account.ensure_url(session.guild.avatar)),
            process=lambda im: ImageOps.fit(im, (64, 64), SCALE_RESAMPLE),
        )
        if session.guild.avatar
        else None
    )

    def make() -> ImageSeg:
        chart = BarChart([Item(count, name=command) for command, count in result])
        chart.title = (
            f"{session.guild.name}\n"
            f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 的命令排行"
        )
        chart.integral_splits = True
        chart.pattern = (
            material_pattern_stripe_from_icon(avatar)
            if avatar
            else DEFAULT_STRIPE_PATTERN
        )
        return to_segment(chart.render())

    return MessageChain(await asyncio.to_thread(make))


hourly_statistics = Alconna(
    "hourly_statistics",
    meta=CommandMeta(
        "查看最近 7 天的消息统计，以小时为单位",
        extra={
            "idhagnbot_i18n_names": {
                "hourly_statistics": "en-US",
                "小时统计": "zh-CN",
            },
        },
    ),
)
hourly_statistics.shortcut("小时统计", command="hourly_statistics")


@command.on(hourly_statistics)
@propagate(require_permission("idhagnbot.charts.hourly_statistics", prompt=True))
async def handle_hourly_statistics(db: AsyncSession, session: Session) -> MessageChain:
    end_date = datetime.now()
    end_date = end_date.replace(
        hour=end_date.hour + 1,
        minute=0,
        second=0,
        microsecond=0,
    )
    start_date = end_date - timedelta(7)
    engine = db.bind
    if engine.dialect.name == "sqlite":
        date_func = func.strftime("%Y-%m-%d %H:00:00", MessageRevision.created_at)
    elif engine.dialect.name == "mysql":
        date_func = func.date_format(MessageRevision.created_at, "%Y-%m-%d %H:00:00")
    elif engine.dialect.name == "postgresql":
        date_func = func.date_trunc("hour", MessageRevision.created_at)
    else:
        raise NotImplementedError(f"不支持的数据库: {engine.dialect.name}")
    result = await db.execute(
        select(date_func, func.count(Message.id))
        .join(
            MessageRevision,
            (Message.platform == MessageRevision.platform)
            & (Message.channel_id == MessageRevision.channel_id)
            & (Message.id == MessageRevision.message_id)
            & (MessageRevision.revision == 1),
        )
        .join(
            Channel,
            (Message.platform == Channel.platform) & (Message.channel_id == Channel.id),
        )
        .where(
            Channel.platform == session.account.platform,
            Channel.guild_id == session.channel.id,
            MessageRevision.created_at >= start_date,
            MessageRevision.created_at <= end_date,
        )
        .group_by(date_func)
        .order_by(date_func),
    )
    result = result.all()
    end_date -= timedelta(seconds=1)  # 显示 x:59:59 而不是 x+1:00:00，以防误会
    avatar = (
        await open_url(
            str(session.account.ensure_url(session.guild.avatar)),
            process=lambda im: ImageOps.fit(im, (64, 64), SCALE_RESAMPLE),
        )
        if session.guild.avatar
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
            f"{session.guild.name}\n"
            f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} 的统计"
        )
        chart.bar_width = 8
        chart.integral_splits = True
        chart.pattern = (
            material_pattern_stripe_from_icon(avatar)
            if avatar
            else DEFAULT_STRIPE_PATTERN
        )
        chart.show_values = False
        return to_segment(chart.render())

    return MessageChain(await asyncio.to_thread(make))
