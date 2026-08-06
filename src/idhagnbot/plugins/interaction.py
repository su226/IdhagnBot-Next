from arclet import letoderea
from arclet.entari import (
    At,
    Author,
    Member,
    MessageObject,
    Reply,
    Session,
    Text,
    User,
    enter_if,
    metadata,
    plugin_config,
)
from arclet.entari.event.base import MessageCreatedEvent
from arclet.letoderea import BLOCK, Contexts, ExitState
from entari_plugin_permission import require_permission
from pydantic import BaseModel
from pydantic.experimental.missing_sentinel import MISSING
from satori import select

from idhagnbot.plugins.record import recorded_non_command


class Config(BaseModel):
    active_prefix: str = "/"
    passive_prefix: str = "\\"
    max_length: int = 10


metadata("", config=Config)
CONFIG = plugin_config(Config)


class ReplyExtractor:
    def __init__(self, event: MessageCreatedEvent, reply: Reply) -> None:
        self.event = event
        self.reply = reply
        self.message: MessageObject | MISSING | None = MISSING
        self.member: Member | MISSING | None = MISSING
        self.user: User | MISSING = MISSING

    async def get_message(self) -> MessageObject | None:
        if self.message is MISSING:
            if self.reply.quote.id is None:
                self.message = None
            else:
                self.message = await self.event.account.message_get(
                    self.event.channel.id,
                    self.reply.quote.id,
                )
        return self.message

    async def get_member(self, author_id: str) -> Member | None:
        if self.member is MISSING:
            if self.event.guild:
                self.member = await self.event.account.guild_member_get(
                    self.event.guild.id,
                    author_id,
                )
            else:
                self.member = None
        return self.member

    async def get_user(self, author_id: str) -> User:
        if self.user is MISSING:
            self.user = await self.event.account.user_get(author_id)
        return self.user

    async def extract_member_nick(self, author_id: str) -> str | None:
        if (
            self.message
            and self.message is not MISSING
            and self.message.member
            and self.message.member.nick
        ):
            return self.message.member.nick
        if self.reply.origin.member and self.reply.origin.member.nick:
            return self.reply.origin.member.nick
        member = await self.get_member(author_id)
        if member and member.nick:
            return member.nick
        return None

    async def extract_user_nick(self, author_id: str) -> str | None:
        if (
            self.message
            and self.message is not MISSING
            and self.message.member
            and self.message.member.user
            and self.message.member.user.nick
        ):
            return self.message.member.user.nick
        if (
            self.reply.origin.member
            and self.reply.origin.member.user
            and self.reply.origin.member.user.nick
        ):
            return self.reply.origin.member.user.nick
        if (
            self.member
            and self.member is not MISSING
            and self.member.user
            and self.member.user.nick
        ):
            return self.member.user.nick
        if self.reply.origin.user and self.reply.origin.user.nick:
            return self.reply.origin.user.nick
        user = await self.get_user(author_id)
        if user and user.nick:
            return user.nick
        return None

    async def extract_user_name(self, author_id: str) -> str | None:
        if (
            self.message
            and self.message is not MISSING
            and self.message.member
            and self.message.member.user
            and self.message.member.user.name
        ):
            return self.message.member.user.name
        if (
            self.reply.origin.member
            and self.reply.origin.member.user
            and self.reply.origin.member.user.name
        ):
            return self.reply.origin.member.user.name
        if (
            self.member
            and self.member is not MISSING
            and self.member.user
            and self.member.user.name
        ):
            return self.member.user.name
        if (
            self.message
            and self.message is not MISSING
            and self.message.user
            and self.message.user.name
        ):
            return self.message.user.name
        if self.reply.origin.user and self.reply.origin.user.name:
            return self.reply.origin.user.name
        user = await self.get_user(author_id)
        if user and user.name:
            return user.name
        return None

    async def extract(self) -> tuple[str, str] | None:
        authors = select(self.reply.quote.children, Author)
        if len(authors) == 1:
            author_id = authors[0].id
            author_name = authors[0].name
            if author_name:
                return author_id, author_name
        elif self.reply.origin.user:
            author_id = self.reply.origin.user.id
        else:
            message = await self.get_message()
            if not message or not message.user:
                return None
            author_id = message.user.id
        member_nick = await self.extract_member_nick(author_id)
        if member_nick:
            return author_id, member_nick
        user_nick = await self.extract_user_nick(author_id)
        if user_nick:
            return author_id, user_nick
        user_name = await self.extract_user_name(author_id)
        if user_name:
            return author_id, user_name
        return author_id, author_id


class AtExtractor:
    def __init__(self, event: MessageCreatedEvent, at: At) -> None:
        self.event = event
        self.at = at
        self.member: Member | MISSING | None = MISSING
        self.user: User | MISSING = MISSING

    async def get_member(self, author_id: str) -> Member | None:
        if self.member is MISSING:
            if self.event.guild:
                self.member = await self.event.account.guild_member_get(
                    self.event.guild.id,
                    author_id,
                )
            else:
                self.member = None
        return self.member

    async def get_user(self, author_id: str) -> User:
        if self.user is MISSING:
            self.user = await self.event.account.user_get(author_id)
        return self.user

    async def extract_member_nick(self, author_id: str) -> str | None:
        member = await self.get_member(author_id)
        if member and member.nick:
            return member.nick
        return None

    async def extract_user_nick(self, author_id: str) -> str | None:
        if (
            self.member
            and self.member is not MISSING
            and self.member.user
            and self.member.user.nick
        ):
            return self.member.user.nick
        user = await self.get_user(author_id)
        if user and user.nick:
            return user.nick
        return None

    async def extract_user_name(self, author_id: str) -> str | None:
        if (
            self.member
            and self.member is not MISSING
            and self.member.user
            and self.member.user.name
        ):
            return self.member.user.name
        user = await self.get_user(author_id)
        if user and user.name:
            return user.name
        return None

    async def extract(self) -> tuple[str, str] | None:
        if not self.at.id:
            return None
        if self.at.name:
            return self.at.id, self.at.name
        member_nick = await self.extract_member_nick(self.at.id)
        if member_nick:
            return self.at.id, member_nick
        user_nick = await self.extract_user_nick(self.at.id)
        if user_nick:
            return self.at.id, user_nick
        user_name = await self.extract_user_name(self.at.id)
        if user_name:
            return self.at.id, user_name
        return self.at.id, self.at.id


async def check_interaction(
    session: Session[MessageCreatedEvent],
    ctx: Contexts,
) -> bool:
    if getattr(session.event, "idhagnbot_executed", False):
        return False
    message = session.elements
    at = message[At]
    if len(at) > 1:
        return False
    text_segments = message[Text]
    if not all(isinstance(segment, (At, Text)) for segment in message):
        return False
    text = text_segments.extract_plain_text().strip()
    if text.startswith(CONFIG.active_prefix):
        action = text[len(CONFIG.active_prefix) :]
        passive = False
    elif text.startswith(CONFIG.passive_prefix):
        action = text[len(CONFIG.passive_prefix) :]
        passive = True
    else:
        return False
    if not action:
        return False
    if len(action) > CONFIG.max_length:
        return False
    reply_user2 = (
        await ReplyExtractor(session.event, session.reply).extract()
        if session.reply
        else None
    )
    at_user2 = await AtExtractor(session.event, at[0]).extract() if at else None
    if reply_user2 and at_user2:
        if reply_user2[0] != at_user2[0]:
            return False
        user2 = at_user2[1]
    elif reply_user2:
        user2 = reply_user2[1]
    elif at_user2:
        user2 = at_user2[1]
    else:
        return False
    ctx["action"] = action
    ctx["passive"] = passive
    ctx["user2"] = user2
    return True


def get_nick(session: Session) -> str:
    if session.event.member and session.event.member.nick:
        return session.event.member.nick
    if session.user.nick:
        return session.user.nick
    if session.user.name:
        return session.user.name
    return session.user.id


@letoderea.on(MessageCreatedEvent)
@recorded_non_command()
@letoderea.propagate(require_permission("idhagnbot.interaction"))
@enter_if(check_interaction)
async def handle_interaction(ctx: Contexts, session: Session) -> ExitState:
    user1 = get_nick(session)
    if ctx["passive"]:
        await session.send([Text(f"{user1} 被 {ctx['user2']} {ctx['action']}了")])
    else:
        await session.send([Text(f"{user1} {ctx['action']}了 {ctx['user2']}")])
    return BLOCK
