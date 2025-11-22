from collections.abc import Awaitable
from typing import TypeVar

import nonebot
from nonebot import logger

__all__ = ["create_background_task"]
_T = TypeVar("_T")
_driver = nonebot.get_driver()


async def _background_task_wrapper(coro: Awaitable[_T]) -> None:
  try:
    await coro
  except Exception as e:
    nonebot.require("idhagnbot.plugins.error")
    from idhagnbot.plugins.error import send_error

    description = "后台任务出错"
    logger.exception(description)
    await send_error("background_task", description, e)


# 不要直接使用 asyncio.create_task
# 参见 https://docs.astral.sh/ruff/rules/asyncio-dangling-task/
def create_background_task(coro: Awaitable[_T]) -> None:
  _driver.task_group.start_soon(_background_task_wrapper, coro)
