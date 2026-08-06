from datetime import date, timedelta
from typing import override

from arclet.entari import MessageChain, Text
from entari_plugin_database import AsyncSession, get_session  # entari: plugin
from sqlalchemy import func, select

from idhagnbot.plugins.daily_push.module import Target, TargetAwareModule
from idhagnbot.plugins.record import Channel, Member, Message, MessageRevision, User
from idhagnbot.support import get_bot_on

EMOJIS = ["🥇", "🥈", "🥉"]


async def get_member_nick(
    db: AsyncSession,
    platform: str,
    guild_id: str,
    user_id: str,
) -> str:
    member = await db.get(Member, (platform, guild_id, user_id))
    if member and member.nick:
        return member.nick
    user = await db.get(User, (platform, user_id))
    if user:
        return user.nick or user.name or user.id
    return user_id


class RankModule(TargetAwareModule):
    type = "rank"

    @override
    async def format(self, target: Target) -> list[MessageChain]:
        if target.guild_id is None:
            return []
        bot = get_bot_on(target.platform)
        if bot is None:
            return []
        today = date.today()
        yesterday = today - timedelta(1)
        async with get_session() as db:
            result = await db.execute(
                select(
                    Message.user_id,
                    count_func := func.count(Message.id),
                )
                .join(
                    MessageRevision,
                    (Message.platform == MessageRevision.platform)
                    & (Message.channel_id == MessageRevision.channel_id)
                    & (Message.id == MessageRevision.message_id)
                    & (MessageRevision.revision == 1),
                )
                .join(
                    Channel,
                    (Message.platform == Channel.platform)
                    & (Message.channel_id == Channel.id),
                )
                .where(
                    Channel.platform == target.platform,
                    Channel.guild_id == target.guild_id,
                    MessageRevision.created_at >= yesterday,
                    MessageRevision.created_at < today,
                    ~Message.outgoing,
                )
                .group_by(Message.user_id)
                .order_by(count_func.desc())
                .limit(10),
            )
            result = list(result)
            if not result:
                return []
            nicks = [
                await get_member_nick(db, target.platform, target.guild_id, user_id)
                for user_id, _ in result
            ]
        lines = ["昨天最能水的成员："]
        for i, (nick, (_, count)) in enumerate(zip(nicks, result, strict=True)):
            prefix = EMOJIS[i] if i < len(EMOJIS) else f"{i + 1}."
            lines.append(f"{prefix} {nick} - {count} 条")
        return [MessageChain(Text("\n".join(lines)))]
