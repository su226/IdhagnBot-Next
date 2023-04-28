import asyncio
import logging
import signal
import sys
from loguru import logger

__all__ = "logger", "config_logger", "wait_shutdown"


class LoguruHandler(logging.Handler):
  def emit(self, record: logging.LogRecord):
    try:
      level = logger.level(record.levelname).name
    except ValueError:
      level = record.levelno

    frame, depth = logging.currentframe(), 2
    while frame and frame.f_code.co_filename == logging.__file__:
      frame = frame.f_back
      depth += 1

    logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def config_logger(name: str, level: str = "INFO") -> None:
  logging.basicConfig(level=level, handlers=[LoguruHandler()])
  logger.configure(
    handlers=[{
      "sink": sys.stdout,
      "level": level,
      "diagnose": False,
      "format": (
        "<g>{time:MM-DD HH:mm:ss}</g> [<lvl>{level}</lvl>] "
        f"<blue>{name}</blue>:"
        "<c><u>{name}</u></c> | {message}"
      ),
    }],
  )


async def wait_shutdown() -> None:
  loop = asyncio.get_running_loop()
  shutdown = asyncio.Event()
  try:
    loop.add_signal_handler(signal.SIGINT, shutdown.set)
    loop.add_signal_handler(signal.SIGTERM, shutdown.set)
  except NotImplementedError:
    signal.signal(signal.SIGINT, lambda sig, frame: shutdown.set())
    signal.signal(signal.SIGTERM, lambda sig, frame: shutdown.set())
  await shutdown.wait()
  try:
    loop.remove_signal_handler(signal.SIGINT)
    loop.remove_signal_handler(signal.SIGTERM)
  except NotImplementedError:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
