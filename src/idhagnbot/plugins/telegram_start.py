from arclet import letoderea
from arclet.entari import MessageCreatedEvent, Session, Text, enter_if
from arclet.entari.event.base import InteractionCommandMessageEvent
from entari_plugin_permission import require_permission
from satori.element import escape

from idhagnbot.i18n import bound_lang
from idhagnbot.plugins.alias import get_prefix

L = bound_lang("idhagnbot_telegram_start")


async def check_start(
    session: Session[MessageCreatedEvent | InteractionCommandMessageEvent],
) -> bool:
    return (
        session.account.platform == "telegram"
        and len(session.event.message.message) == 1
        and isinstance(segment := session.event.message.message[0], Text)
        and segment.text == "/start"
    )


@letoderea.on(MessageCreatedEvent)
@letoderea.on(InteractionCommandMessageEvent)
@letoderea.propagate(require_permission("idhagnbot.telegram_start", prompt=True))
@enter_if(check_start)
async def handle_start(session: Session) -> None:
    prefix = get_prefix("telegram")
    await session.message_create(escape(L("start").format(prefix=prefix)))
