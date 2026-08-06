import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from arclet.alconna import Alconna, Args, CommandMeta
from arclet.entari import (
    Account,
    MessageChain,
    MessageCreatedEvent,
    Session,
    Text,
    command,
    metadata,
    plugin_config,
)
from arclet.entari import Image as ImageSeg
from arclet.entari.command import Match
from arclet.letoderea import Contexts, enter_if, on
from entari_plugin_database import AsyncSession, Base  # entari: plugin
from entari_plugin_permission import require_permission
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.asyncio import gather_seq
from idhagnbot.datetime import DATE_ARGS_USAGE, parse_date_range
from idhagnbot.image import (
    SCALE_RESAMPLE,
    open_url,
    resize_height,
    to_segment,
)
from idhagnbot.image.bar_chart import (
    DEFAULT_STRIPE_PATTERN,
    BarChart,
    Item,
    material_palette_from_icon,
    material_pattern_stripe_from_icon,
)
from idhagnbot.meme_common import get_member, get_user
from idhagnbot.plugins.alias import has_command_prefix


class Counter(BaseModel):
    id: str
    name: str
    patterns: list[re.Pattern[str]]
    exclude: list[re.Pattern[str]] = Field(default_factory=list)
    match_rank: bool = False
    group: int | str = Field(default=0)


class Config(BaseModel):
    counters: list[Counter] = Field(default_factory=list)


class Counted(Base):
    __tablename__ = "idhagnbot_regex_counter_counted"
    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[datetime]
    platform: Mapped[str]
    channel_id: Mapped[str]
    counter_id: Mapped[str]
    user_id: Mapped[str]
    match: Mapped[str]


metadata("", config=Config)
CONFIG = plugin_config(Config)


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


@dataclass
class CounterHandlers:
    counter: Counter

    async def check_count(self, session: Session, ctx: Contexts) -> bool:
        if has_command_prefix(session.account.platform, session.elements):
            return False
        matches = list[str]()
        for text in session.elements[Text]:
            for pattern in self.counter.patterns:
                for match in pattern.finditer(text.text):
                    content = match[self.counter.group]
                    excluded = False
                    for exclude_pattern in self.counter.exclude:
                        if exclude_pattern.search(content):
                            excluded = True
                            break
                    if not excluded:
                        matches.append(content)
        if matches:
            ctx["matches"] = matches
            return True
        return False

    async def handle_count(
        self,
        session: Session,
        ctx: Contexts,
        db: AsyncSession,
    ) -> None:
        matches: list[str] = ctx["matches"]
        for match in matches:
            db.add(
                Counted(
                    time=session.event.timestamp,
                    platform=session.account.platform,
                    channel_id=session.channel.id,
                    counter_id=self.counter.id,
                    user_id=session.user.id,
                    match=match,
                ),
            )
        await db.commit()

    async def handle_group_statistics(
        self,
        start: Match[str | None],
        end: Match[str | None],
        session: Session,
        db: AsyncSession,
    ) -> str:
        start_date, end_date = parse_date_range(start.result, end.result)
        result = await db.execute(
            select(func.count())
            .select_from(Counted)
            .where(
                Counted.platform == session.account.platform,
                Counted.channel_id == session.channel.id,
                Counted.counter_id == self.counter.id,
                Counted.time >= start_date,
                Counted.time <= end_date,
            ),
        )
        count = result.scalar_one()
        end_date -= timedelta(seconds=1)
        return (
            f"{session.guild.name} 内 {start_date:%Y-%m-%d %H:%M:%S} 到 "
            f"{end_date:%Y-%m-%d %H:%M:%S} 的{self.counter.name}次数为 {count}。"
        )

    async def handle_user_statistics(
        self,
        start: Match[str | None],
        end: Match[str | None],
        session: Session,
        db: AsyncSession,
    ) -> str:
        start_date, end_date = parse_date_range(start.result, end.result)
        result = await db.execute(
            select(func.count())
            .select_from(Counted)
            .where(
                Counted.platform == session.account.platform,
                Counted.channel_id == session.channel.id,
                Counted.user_id == session.user.id,
                Counted.counter_id == self.counter.id,
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
        return (
            f"{member_name} 在 {session.guild.name} 内 {start_date:%Y-%m-%d %H:%M:%S} "
            f"到 {end_date:%Y-%m-%d %H:%M:%S} 的{self.counter.name}次数为 {count}。"
        )

    async def handle_user_rank(
        self,
        start: Match[str | None],
        end: Match[str | None],
        session: Session,
        db: AsyncSession,
    ) -> str | MessageChain:
        start_date, end_date = parse_date_range(start.result, end.result)
        result = await db.execute(
            select(Counted.user_id, count := func.count(Counted.user_id))
            .where(
                Counted.platform == session.account.platform,
                Counted.channel_id == session.channel.id,
                Counted.counter_id == self.counter.id,
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
            return (
                f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} "
                "内没有数据"
            )
        names_and_avatars = await gather_seq(
            get_name_and_avatar(session, user_id) for user_id, _ in result
        )

        def make() -> ImageSeg:
            chart = BarChart()
            chart.title = (
                f"{session.guild.name}\n{start_date:%Y-%m-%d %H:%M:%S} 到 "
                f"{end_date:%Y-%m-%d %H:%M:%S} 的{self.counter.name}次数排行"
            )
            chart.integral_splits = True
            items = list[Item]()
            for (_, count), (name, avatar) in zip(
                result,
                names_and_avatars,
                strict=True,
            ):
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

    async def handle_match_rank_group(
        self,
        start: Match[str | None],
        end: Match[str | None],
        session: Session,
        db: AsyncSession,
    ) -> str | MessageChain:
        start_date, end_date = parse_date_range(start.result, end.result)
        result = await db.execute(
            select(Counted.match, count := func.count(Counted.match))
            .where(
                Counted.platform == session.account.platform,
                Counted.channel_id == session.channel.id,
                Counted.counter_id == self.counter.id,
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
            return (
                f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} "
                "内没有数据"
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
            chart = BarChart([Item(count, name=match) for match, count in result])
            chart.title = (
                f"{session.guild.name}\n{start_date:%Y-%m-%d %H:%M:%S} 到 "
                f"{end_date:%Y-%m-%d %H:%M:%S} 的{self.counter.name}内容排行"
            )
            chart.integral_splits = True
            chart.pattern = (
                material_pattern_stripe_from_icon(avatar)
                if avatar
                else DEFAULT_STRIPE_PATTERN
            )
            return to_segment(chart.render())

        return MessageChain(await asyncio.to_thread(make))

    async def handle_match_rank_user(
        self,
        start: Match[str | None],
        end: Match[str | None],
        session: Session,
        db: AsyncSession,
    ) -> str | MessageChain:
        start_date, end_date = parse_date_range(start.result, end.result)
        result = await db.execute(
            select(Counted.match, count := func.count(Counted.match))
            .where(
                Counted.platform == session.account.platform,
                Counted.channel_id == session.channel.id,
                Counted.user_id == session.user.id,
                Counted.counter_id == self.counter.id,
                Counted.time >= start_date,
                Counted.time <= end_date,
            )
            .group_by(Counted.match)
            .order_by(count.desc())
            .limit(20),
        )
        end_date -= timedelta(seconds=1)
        if not result:
            return (
                f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} "
                "内没有数据"
            )
        avatar = (
            await open_url(
                str(session.account.ensure_url(session.user.avatar)),
                process=lambda im: ImageOps.fit(im, (64, 64), SCALE_RESAMPLE),
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
                f"{member_name} 在 {session.guild.name} 内\n"
                f"{start_date:%Y-%m-%d %H:%M:%S} 到 {end_date:%Y-%m-%d %H:%M:%S} "
                f"的{self.counter.name}内容排行"
            )
            chart.integral_splits = True
            chart.pattern = (
                material_pattern_stripe_from_icon(avatar)
                if avatar
                else DEFAULT_STRIPE_PATTERN
            )
            return to_segment(chart.render())

        return MessageChain(await asyncio.to_thread(make))

    def register(self) -> None:
        on(MessageCreatedEvent)(self.handle_count).propagate(enter_if(self.check_count))
        command.on(
            Alconna(
                f"群{counter.name}统计",
                Args["start?", str, None],
                Args["end?", str, None],
                meta=CommandMeta(
                    f"群内总{counter.name}次数统计",
                    usage=DATE_ARGS_USAGE,
                ),
            ),
        )(self.handle_group_statistics).propagate(
            require_permission(
                f"idhagnbot.regex_counter.{self.counter.id}.statistics.group",
                prompt=True,
            ),
        )
        command.on(
            Alconna(
                f"个人{counter.name}统计",
                Args["start?", str, None],
                Args["end?", str, None],
                meta=CommandMeta(f"个人{counter.name}次数统计", usage=DATE_ARGS_USAGE),
            ),
        )(self.handle_user_statistics).propagate(
            require_permission(
                f"idhagnbot.regex_counter.{self.counter.id}.statistics.user",
                prompt=True,
            ),
        )
        command.on(
            Alconna(
                f"{counter.name}排行",
                Args["start?", str, None],
                Args["end?", str, None],
                meta=CommandMeta(
                    f"群内总{counter.name}次数按群成员排行",
                    usage=DATE_ARGS_USAGE,
                ),
            ),
        )(self.handle_user_rank).propagate(
            require_permission(
                f"idhagnbot.regex_counter.{self.counter.id}.rank",
                prompt=True,
            ),
        )
        if counter.match_rank:
            command.on(
                Alconna(
                    f"群{counter.name}内容排行",
                    Args["start?", str, None],
                    Args["end?", str, None],
                    meta=CommandMeta(
                        f"群内总{counter.name}次数按内容排行",
                        usage=DATE_ARGS_USAGE,
                    ),
                ),
            )(self.handle_match_rank_group).propagate(
                require_permission(
                    f"idhagnbot.regex_counter.{self.counter.id}.match_rank.group",
                    prompt=True,
                ),
            )
            command.on(
                Alconna(
                    f"个人{counter.name}内容排行",
                    Args["start?", str, None],
                    Args["end?", str, None],
                    meta=CommandMeta(
                        f"个人{counter.name}次数按内容排行",
                        usage=DATE_ARGS_USAGE,
                    ),
                ),
            )(self.handle_match_rank_user).propagate(
                require_permission(
                    f"idhagnbot.regex_counter.{self.counter.id}.match_rank.user",
                    prompt=True,
                ),
            )


for counter in CONFIG.counters:
    CounterHandlers(counter).register()
