import asyncio
import multiprocessing as mp
from typing import List, Literal, Optional, Tuple
from loguru import logger

import abc
import nonebot
from pydantic import BaseModel, Field, SecretStr


class ImplConfig(BaseModel, abc.ABC):
  type: str

  @abc.abstractmethod
  def spawn(self) -> mp.Process: ...


class TelegramImplConfig(ImplConfig):
  type: Literal["telegram"]
  api_id: int
  api_hash: SecretStr
  bot_token: SecretStr
  proxy: str = ""

  def __repr__(self) -> str:
    bot_id = self.bot_token.get_secret_value().split(":", 1)[0]
    return (
      f"<telegram_obimpl api={self.api_id}:********** bot={bot_id}:********** "
      f"proxy={self.proxy!r}>"
    )

  def spawn(self) -> mp.Process:
    from idhagnbot.plugins.ob12impl_autostart.telegram import start
    process = mp.Process(target=start, args=(
      self.api_id,
      self.api_hash.get_secret_value(),
      self.bot_token.get_secret_value(),
      self.proxy,
      NONEBOT_CONFIG.port,
      NONEBOT_CONFIG.log_level,
    ))
    process.start()
    return process


class Config(BaseModel):
  ob12impl_autostart: List[TelegramImplConfig] = Field(default_factory=list)
  ob12impl_exit_timeout: int = 10


DRIVER = nonebot.get_driver()
NONEBOT_CONFIG = DRIVER.config
CONFIG = Config.parse_obj(NONEBOT_CONFIG)
processes: List[Tuple[ImplConfig, mp.Process]] = []
monitor_task: Optional[asyncio.Task] = None


async def monitor() -> None:
  while True:
    await asyncio.sleep(1)
    try:
      for i, (impl, process) in enumerate(processes):
        if process.exitcode is not None:
          logger.warning(f"OneBot 协议端 {impl} 意外退出了，退出代码: {process.exitcode}")
          processes[i] = (impl, impl.spawn())
    except Exception:
      logger.opt(exception=True).warning("监视 OneBot 协议端进程时发生了意外的错误。")


@DRIVER.on_startup
async def on_startup() -> None:
  for impl in CONFIG.ob12impl_autostart:
    processes.append((impl, impl.spawn()))
  if CONFIG.ob12impl_autostart:
    global monitor_task
    monitor_task = asyncio.create_task(monitor())


@DRIVER.on_shutdown
async def on_shutdown() -> None:
  if monitor_task:
    monitor_task.cancel()
    try:
      await monitor_task
    except asyncio.CancelledError:
      pass
  if processes:
    logger.info("等待 OneBot 协议端退出……")
    seconds = 0
    while any(process.exitcode is None for _, process in processes):
      if seconds >= CONFIG.ob12impl_exit_timeout:
        logger.info("OneBot 协议端退出超时，强行停止中……")
        for _, process in processes:
          process.kill()
        break
      for _, process in processes:
        process.terminate()
      await asyncio.sleep(1)
      seconds += 1
