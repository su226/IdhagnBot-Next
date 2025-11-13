import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")
background_tasks = set[asyncio.Task[Any]]()


# https://docs.astral.sh/ruff/rules/asyncio-dangling-task/
def create_background_task(coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
  task = asyncio.create_task(coro)
  background_tasks.add(task)
  task.add_done_callback(background_tasks.discard)
  return task
