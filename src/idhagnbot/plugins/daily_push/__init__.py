from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from itertools import chain

from arclet.alconna import Alconna, CommandMeta, Option, store_true
from arclet.entari import (
    MessageChain,
    Plugin,
    Ready,
    Session,
    Text,
    command,
    metadata,
    plugin_config,
)
from arclet.entari.scheduler import cron
from arclet.letoderea import on, propagate
from croniter import croniter
from entari_plugin_database import get_session  # entari: plugin
from entari_plugin_permission import require_permission  # entari: plugin
from loguru import logger
from pydantic import BaseModel, Field
from satori.exception import ActionFailed

from idhagnbot.asyncio import create_background_task, gather_seq
from idhagnbot.data import SharedCache
from idhagnbot.plugins.alias import get_prefix
from idhagnbot.plugins.daily_push.module import Target, register
from idhagnbot.plugins.daily_push.modules.constant import ConstantModule
from idhagnbot.plugins.daily_push.modules.countdown import CountdownModule
from idhagnbot.plugins.daily_push.modules.group import GroupModule
from idhagnbot.plugins.daily_push.modules.rank import RankModule
from idhagnbot.plugins.error_report import send_error
from idhagnbot.plugins.record import Channel
from idhagnbot.support import get_bot_on


class Push(GroupModule):
    cron: str
    targets: list[str]


class Config(BaseModel):
    pushes: dict[str, Push] = Field(default_factory=dict)
    grace_time: timedelta = timedelta(minutes=10)


class Cache(BaseModel):
    last_check: dict[str, datetime] = Field(default_factory=dict)


metadata("", config=Config)
CONFIG = plugin_config(Config)
CACHE = SharedCache("daily_push", Cache)
PLUGIN = Plugin.current()
PLUGIN.collect(register(ConstantModule))
PLUGIN.collect(register(CountdownModule))
PLUGIN.collect(register(GroupModule))
PLUGIN.collect(register(RankModule))


async def check_push(push_id: str) -> None:
    data = CACHE()
    push = CONFIG.pushes[push_id]
    now = datetime.now()
    send_datetime = croniter(push.cron, now, datetime).get_prev()
    if send_datetime <= data.last_check.get(push_id, datetime.min):
        return
    if now > send_datetime + CONFIG.grace_time:
        logger.warning(f"超过最大发送时间，将不会发送每日推送 {push_id}")
    else:
        logger.info(f"发送每日推送 {push_id}")
        await send_push(push)
    data.last_check[push_id] = now
    CACHE.dump()


for push_id, push_config in CONFIG.pushes.items():
    cron(push_config.cron, label=f"idhagnbot-cron_push-{push_id}")(
        lambda push_id=push_id: check_push(push_id),
    )


@on(Ready)
async def on_ready() -> None:
    for push_id in CONFIG.pushes:
        create_background_task(check_push(push_id))


async def send_one(target: Target, messages: list[MessageChain]) -> None:
    bot = get_bot_on(target.platform)
    if bot is None:
        return
    failed = False
    for message in messages:
        try:
            await bot.send_message(target.channel_id, message)
        except ActionFailed as e:
            description = f"推送到目标 {target.platform}:{target.channel_id} 失败"
            logger.exception(f"{description}: {message}")
            create_background_task(send_error("daily_push", description, e))
            failed = True
    if failed:
        try:
            prefix = get_prefix(target.platform)
            await bot.send_message(
                target.channel_id,
                [Text(f"发送部分每日推送失败，可运行 {prefix}每日推送 重新查看")],
            )
        except ActionFailed:
            pass


async def send_push(push: Push) -> None:
    targets = []
    async with get_session() as db:
        for target in push.targets:
            platform, channel_id = target.split(":", maxsplit=1)
            channel = await db.get(Channel, (platform, channel_id))
            guild_id = channel.guild_id if channel else None
            targets.append(Target(platform, guild_id, channel_id))
    results = await push.format(targets)
    await gather_seq(send_one(target, messages) for target, messages in results.items())


async def format_pushes(session: Session, channel: bool) -> list[MessageChain]:
    if channel or session.event.guild is None:
        current = f"{session.account.platform}:{session.channel.id}"
        pushes = [
            push
            for push in CONFIG.pushes.values()
            if any(target == current for target in push.targets)
        ]
    else:
        pushes = []
        async with get_session() as db:
            for push in CONFIG.pushes.values():
                for target in push.targets:
                    platform, channel_id = target.split(":", maxsplit=1)
                    chan = await db.get(Channel, (platform, channel_id))
                    if chan and chan.guild_id == session.event.guild.id:
                        pushes.append(push)
                        break
    target = Target(
        session.account.platform,
        (None if session.event.guild is None else session.event.guild.id),
        session.channel.id,
    )
    contents = await gather_seq(push.format([target]) for push in pushes)
    return list(chain.from_iterable(content[target] for content in contents))


@command.on(
    Alconna(
        "每日推送",
        Option("-c|--channel", action=store_true, dest="channel", default=False),
        meta=CommandMeta("重新发送每日推送"),
    ),
)
@propagate(require_permission("idhagnbot.daily_push", prompt=True))
async def handle_resend_push(
    channel: bool,
    session: Session,
) -> AsyncGenerator[str | MessageChain]:
    messages = await format_pushes(session, channel)
    if messages:
        for message in messages:
            yield message
    elif channel and session.event.guild is not None:
        yield "当前会话没有每日推送（请检查是否在正确的子频道）"
    else:
        yield "当前会话没有每日推送"
