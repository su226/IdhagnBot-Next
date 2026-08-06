from itertools import chain

from arclet import letoderea
from arclet.entari import (
    Message,
    MessageChain,
    SendRequest,
    SendResponse,
    Session,
    enter_if,
)
from arclet.entari.event.base import (
    MessageCreatedEvent,
    MessageDeletedEvent,
    MessageEvent,
    MessageUpdatedEvent,
)
from entari_plugin_database import AsyncSession  # entari: plugin
from satori.exception import ActionFailed

from idhagnbot.plugins.alias import has_command_prefix
from idhagnbot.plugins.repeat.common import (
    ALREADY_COUNTED,
    CONDITION_REGISTRY,
    CONFIG,
    FILTER,
    HANDLER_REGISTRY,
    LastMessage,
    count_recall,
    count_received,
    count_send,
    count_sending,
    count_sent,
    is_same,
)
from idhagnbot.plugins.repeat.onebot import register as register_onebot

register_onebot()


@letoderea.on(MessageCreatedEvent, priority=-950)
async def record_received_message(event: MessageCreatedEvent) -> None:
    if ALREADY_COUNTED.get():
        return
    await count_received(event.account.platform, event.channel.id, event.content)


@letoderea.on(MessageDeletedEvent, priority=-950)
@letoderea.on(MessageUpdatedEvent, priority=-950)
async def handle_recall(event: MessageEvent) -> None:
    await count_recall(event.account.platform, event.channel.id)


@letoderea.on(SendRequest)
async def record_sending_message(event: SendRequest) -> None:
    if ALREADY_COUNTED.get():
        return
    await count_sending(event.account.platform, event.channel, event.message)


@letoderea.on(SendResponse)
async def record_sent_message(event: SendResponse) -> None:
    if ALREADY_COUNTED.get():
        return
    message = MessageChain(
        chain.from_iterable(message.message for message in event.result),
    )
    await count_sent(event.account.platform, event.channel, message)


# No way to record send failed.


def is_ignored(platform: str, channel_id: str, message: MessageChain) -> bool:
    text = message.extract_plain_text()
    if patterns := CONFIG.ignore.get("global"):
        for pattern in patterns:
            if pattern.search(text):
                return True
    if patterns := CONFIG.ignore.get(platform):
        for pattern in patterns:
            if pattern.search(text):
                return True
    if patterns := CONFIG.ignore.get(f"{platform}:{channel_id}"):
        for pattern in patterns:
            if pattern.search(text):
                return True
    return False


def check_condition(adapter: str, message: MessageChain) -> bool:
    if condition := CONDITION_REGISTRY.get(adapter):
        return condition(message)
    return True


async def can_repeat(
    session: Session[MessageCreatedEvent],
    db: AsyncSession,
    is_reply_me: bool,
    is_notice_me: bool,
) -> bool:
    platform = session.event.account.platform
    channel_id = session.event.channel.id
    message = session.event.content
    if (
        session.event.guild is not None
        and not has_command_prefix(platform, message)
        and not is_ignored(platform, channel_id, message)
        and await FILTER(session, is_reply_me, is_notice_me)
        and check_condition(platform, message)
        and (last := await db.get(LastMessage, (platform, channel_id)))
        and is_same(platform, message, last)
    ):
        send_count = last.sent_count + last.sending_count
        if (
            send_count < last.received_count // CONFIG.repeat_every
            and send_count < CONFIG.max_repeat
        ):
            return True
    return False


@letoderea.on(MessageCreatedEvent, priority=100)
@enter_if(can_repeat)
async def repeat(session: Session[MessageCreatedEvent]) -> None:
    try:
        if handler := HANDLER_REGISTRY.get(session.account.platform):
            await handler(session.event)
        else:
            async with count_send(
                session.account.platform,
                session.channel.id,
                session.elements,
            ):
                result = await session.send(
                    [Message(session.event.message.id, forward=True)],
                )
                if not result:
                    await session.send(session.elements)
    except ActionFailed:
        pass
