import time

from arclet import letoderea
from arclet.entari import Account, AccountUpdate, Cleanup, Startup, local_data
from arclet.entari.config import EntariConfig
from arclet.entari.scheduler import every
from loguru import logger
from satori import LoginStatus

from idhagnbot.asyncio import delayed
from idhagnbot.plugins.offline_warn.common import (
    CONFIG,
    queue_message,
    send_queued_messages,
)
from idhagnbot.support import current_entari

try:
    import idhagnbot.plugins.offline_warn.onebot  # noqa: F401
except ImportError:
    pass


FILENAME = local_data.get_cache_file("idhagnbot", "poweroff_warn.txt")
shutting_down = False


@letoderea.on(Startup)
async def on_startup() -> None:
    if FILENAME.exists():
        with FILENAME.open() as f:
            crash_str = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(float(f.read())),
            )
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            prefix = f"机器人在 {crash_str} 到 {now_str} 之间可能有非正常退出"
            if EntariConfig.instance.env_vars.get("ENVIRONMENT", "prod") == "dev":
                logger.info(prefix + "，但当前处于调试模式，将不会发送警告。")
            else:
                logger.warning(prefix + "，将发送警告！")
                await queue_message(prefix + "，请注意！")
    write_timestamp()


def write_timestamp() -> None:
    with FILENAME.open("w") as f:
        f.write(str(time.time()))


every(1, "minute", "idhagnbot-offline_warn-write_timestamp")(write_timestamp)


@letoderea.on(Cleanup)
async def on_shutdown() -> None:
    global shutting_down
    shutting_down = True
    FILENAME.unlink()


def is_online(platform: str, self_id: str) -> bool:
    for account in current_entari().accounts.values():
        if account.platform == platform and account.self_id == self_id:
            return account.self_info.status is LoginStatus.ONLINE
    return False


@letoderea.on(AccountUpdate)
async def on_account_update(event: AccountUpdate, account: Account) -> None:
    account.self_info.status = event.status
    if shutting_down:
        return
    if event.status is LoginStatus.ONLINE:
        await send_queued_messages()
        return
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    platform = account.platform
    self_id = account.self_id
    prefix = f"后端 {platform}:{self_id} 在 {now_str} 左右断开"
    seconds = CONFIG.disconnect_grace_time.total_seconds()
    logger.warning(f"{prefix}，将在 {seconds} 秒后发送警告！")

    @delayed(CONFIG.disconnect_grace_time)
    async def queeu_message_if_offline() -> None:
        if not is_online(platform, self_id):
            logger.debug("后端未在时限内重连，发送警告。")
            await queue_message(f"{prefix}，请注意！")
        else:
            logger.debug("后端在时限内重连，不发送警告。")
