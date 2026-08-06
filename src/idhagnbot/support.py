from arclet.entari import Account, Entari
from satori import LoginStatus


def current_entari() -> Entari:
    return Entari.current()


def get_bot_on(platform: str) -> Account | None:
    for bot in current_entari().accounts.values():
        if bot.platform == platform and bot.self_info.status is LoginStatus.ONLINE:
            return bot
    return None


def support_batch_forward(platform: str) -> bool:
    return platform in ("onebot", "milky")


def support_button(platform: str) -> bool:
    return platform in ("telegram", "discord")
