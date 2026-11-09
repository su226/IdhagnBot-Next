from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from arclet.entari import MessageCreatedEvent, Plugin, Session
from arclet.letoderea import STOP, ExitState
from arclet.letoderea.scope import SubscriberSlot
from entari_plugin_user import UserSession as UserSessionDepend
from entari_plugin_user.models import UserSession
from loguru import logger

from idhagnbot.hook import hook_subscriber
from idhagnbot.plugins.alias import has_command_prefix_cached

PLUGIN = Plugin.current()


async def stop_buffer_subscriber() -> ExitState:
    return STOP


async def stop_chat_subscriber(
    session: Session[MessageCreatedEvent],
) -> ExitState | None:
    if getattr(session.event, "idhagnbot_executed", False) or has_command_prefix_cached(
        session.event,
    ):
        logger.trace("Stop LLM chat execution due to command.")
        return STOP
    return None


@dataclass
class HookedBufferHandler:
    orig_callable: Callable[[UserSession, MessageCreatedEvent], Awaitable[None]]

    async def handle(
        self,
        session: UserSessionDepend,
        event: MessageCreatedEvent,
    ) -> None:
        if has_command_prefix_cached(event):
            return
        await self.orig_callable(session, event)


def hook_buffer_subscriber(plugin_id: str, slot: SubscriberSlot) -> None:
    logger.trace(f"Hooking LLM buffer subscriber {slot.subscriber}.")
    PLUGIN.collect(
        slot.subscriber.propagate(stop_buffer_subscriber, prepend=True, priority=-1000),
    )
    PLUGIN.dispatch(MessageCreatedEvent).register(
        HookedBufferHandler(slot.subscriber.callable_target).handle,
        priority=-950,
    )


def hook_chat_subscriber(plugin_id: str, slot: SubscriberSlot) -> None:
    logger.trace(f"Hooking LLM chat subscriber {slot.subscriber}.")
    PLUGIN.collect(
        slot.subscriber.propagate(stop_chat_subscriber, prepend=True, priority=-1000),
    )


PLUGIN.collect(
    hook_subscriber(
        "entari_plugin_llm.handlers.chat",
        "群聊上下文缓存",
        hook_buffer_subscriber,
    ),
)
PLUGIN.collect(
    hook_subscriber("entari_plugin_llm.handlers.chat", "AI-对话", hook_chat_subscriber),
)
