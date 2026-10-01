import random
from collections.abc import Sequence
from itertools import chain

from arclet.entari import (
    Element,
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
from arclet.letoderea import Contexts, on
from entari_plugin_database import AsyncSession  # entari: plugin
from satori.exception import ActionFailed

from idhagnbot.plugins.alias import has_command_prefix
from idhagnbot.plugins.repeat.common import (
    ALREADY_COUNTED,
    CONDITION_REGISTRY,
    CONFIG,
    HANDLER_REGISTRY,
    LastMessage,
    OverridableConfig,
    count_recall,
    count_received,
    count_send,
    count_sending,
    count_sent,
    is_same,
)
from idhagnbot.plugins.repeat.onebot import register as register_onebot

register_onebot()


@on(MessageCreatedEvent, priority=-950)
async def record_received_message(event: MessageCreatedEvent) -> None:
    if ALREADY_COUNTED.get():
        return
    await count_received(event.account.platform, event.channel.id, event.content)


@on(MessageDeletedEvent, priority=-950)
@on(MessageUpdatedEvent, priority=-950)
async def handle_recall(event: MessageEvent) -> None:
    await count_recall(event.account.platform, event.channel.id)


@on(SendRequest)
async def record_sending_message(event: SendRequest) -> None:
    if ALREADY_COUNTED.get():
        return
    await count_sending(event.account.platform, event.channel, event.message)


@on(SendResponse)
async def record_sent_message(event: SendResponse) -> None:
    if ALREADY_COUNTED.get():
        return
    message = MessageChain(
        chain.from_iterable(message.message for message in event.result),
    )
    await count_sent(event.account.platform, event.channel, message)


# No way to record send failed.


def check_condition(adapter: str, message: Sequence[Element]) -> bool:
    if condition := CONDITION_REGISTRY.get(adapter):
        return condition(message)
    return True


async def can_repeat(
    session: Session[MessageCreatedEvent],
    db: AsyncSession,
    ctx: Contexts,
) -> bool:
    if session.event.guild is None:
        return False
    platform = session.event.account.platform
    guild_id = session.event.guild.id
    channel_id = session.event.channel.id
    message = session.event.message.message
    if (
        not has_command_prefix(platform, message)
        and not CONFIG.is_ignored_in(platform, guild_id, channel_id, message)
        and check_condition(platform, message)
        and (last := await db.get(LastMessage, (platform, channel_id)))
        and is_same(platform, message, last)
    ):
        send_count = last.sent_count + last.sending_count
        config = CONFIG.get_overridable_config_in(platform, guild_id, channel_id)
        if (
            last.received_count > 1
            and send_count < last.received_count // config.every
            and send_count < config.max
            and random.uniform(0, 1) < config.chance
        ):
            ctx["config"] = config
            return True
    return False


@on(MessageCreatedEvent, priority=100)
@enter_if(can_repeat)
async def repeat(session: Session[MessageCreatedEvent], ctx: Contexts) -> None:
    try:
        config: OverridableConfig = ctx["config"]
        if random.uniform(0, 1) < config.special_chance:
            await session.send(config.special)
            return
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
