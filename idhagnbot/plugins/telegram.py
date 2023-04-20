import nonebot
from nonebot.adapters.onebot.v12 import Bot, Message, MessageEvent, MessageSegment as S
from pydantic import BaseModel

from idhagnbot.args import NoArg, on_prefix_command

# Telegram 特定行为
# 目前仅处理 /start 命令


class Config(BaseModel):
  telegram_start_extra: str = ""
CONFIG = Config.parse_obj(nonebot.get_driver().config)


def check_start(bot: Bot, event: MessageEvent) -> bool:
  return bot.platform == "telegram" and event.detail_type == "private"
# Telegram 强制命令使用 / 开头
start = on_prefix_command("/", "start", check_start)
@start.handle([NoArg()])
async def handle_start():
  await start.finish(Message([
    S.text("欢迎使用 "),
    S.text("IdhagnBot Next", **{"tg.bold": True}),
    S.text("！\n目前该 Bot 还处于极其早期的阶段，非常不稳定。" + CONFIG.telegram_start_extra),
  ]))
