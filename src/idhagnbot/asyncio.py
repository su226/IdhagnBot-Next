from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any, Literal, TypeVar, cast, overload

import anyio
import nonebot
from nonebot import logger

__all__ = ["create_background_task", "gather", "gather_seq"]
_T = TypeVar("_T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")
_T6 = TypeVar("_T6")
_driver = nonebot.get_driver()
BackgroundExceptionHandler = Callable[[Exception], Awaitable[None]]
TBackgroundExceptionHandler = TypeVar(
  "TBackgroundExceptionHandler",
  bound=BackgroundExceptionHandler,
)
_background_exception_handlers = list[BackgroundExceptionHandler]()


async def _background_task_wrapper(coro: Awaitable[_T]) -> None:
  try:
    await coro
  except Exception as e:
    try:
      async with anyio.create_task_group() as tg:
        for handler in _background_exception_handlers:
          tg.start_soon(handler, e)
    except BaseException:
      logger.exception("运行后台任务错误回调时出错")


# 不要直接使用 asyncio.create_task
# 参见 https://docs.astral.sh/ruff/rules/asyncio-dangling-task/
def create_background_task(coro: Awaitable[_T]) -> None:
  _driver.task_group.start_soon(_background_task_wrapper, coro)


def background_exception_handler(func: TBackgroundExceptionHandler) -> TBackgroundExceptionHandler:
  _background_exception_handlers.append(func)
  return func


@overload
async def gather(
  coro_or_future1: Awaitable[_T1],
  /,
  *,
  return_exceptions: Literal[False] = False,
) -> tuple[_T1]: ...
@overload
async def gather(
  coro_or_future1: Awaitable[_T1],
  coro_or_future2: Awaitable[_T2],
  /,
  *,
  return_exceptions: Literal[False] = False,
) -> tuple[_T1, _T2]: ...
@overload
async def gather(
  coro_or_future1: Awaitable[_T1],
  coro_or_future2: Awaitable[_T2],
  coro_or_future3: Awaitable[_T3],
  /,
  *,
  return_exceptions: Literal[False] = False,
) -> tuple[_T1, _T2, _T3]: ...
@overload
async def gather(
  coro_or_future1: Awaitable[_T1],
  coro_or_future2: Awaitable[_T2],
  coro_or_future3: Awaitable[_T3],
  coro_or_future4: Awaitable[_T4],
  /,
  *,
  return_exceptions: Literal[False] = False,
) -> tuple[_T1, _T2, _T3, _T4]: ...
@overload
async def gather(
  coro_or_future1: Awaitable[_T1],
  coro_or_future2: Awaitable[_T2],
  coro_or_future3: Awaitable[_T3],
  coro_or_future4: Awaitable[_T4],
  coro_or_future5: Awaitable[_T5],
  /,
  *,
  return_exceptions: Literal[False] = False,
) -> tuple[_T1, _T2, _T3, _T4, _T5]: ...
@overload
async def gather(
  coro_or_future1: Awaitable[_T1],
  coro_or_future2: Awaitable[_T2],
  coro_or_future3: Awaitable[_T3],
  coro_or_future4: Awaitable[_T4],
  coro_or_future5: Awaitable[_T5],
  coro_or_future6: Awaitable[_T6],
  /,
  *,
  return_exceptions: Literal[False] = False,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6]: ...
@overload
async def gather(
  *coros: Awaitable[_T],
  return_exceptions: Literal[False] = False,
) -> tuple[_T, ...]: ...
@overload
async def gather(
  coro1: Awaitable[_T1],
  /,
  *,
  return_exceptions: Literal[True],
) -> tuple[_T1 | BaseException]: ...
@overload
async def gather(
  coro1: Awaitable[_T1],
  coro2: Awaitable[_T2],
  /,
  *,
  return_exceptions: Literal[True],
) -> tuple[
  _T1 | BaseException,
  _T2 | BaseException,
]: ...
@overload
async def gather(
  coro1: Awaitable[_T1],
  coro2: Awaitable[_T2],
  coro3: Awaitable[_T3],
  /,
  *,
  return_exceptions: Literal[True],
) -> tuple[
  _T1 | BaseException,
  _T2 | BaseException,
  _T3 | BaseException,
]: ...
@overload
async def gather(
  coro1: Awaitable[_T1],
  coro2: Awaitable[_T2],
  coro3: Awaitable[_T3],
  coro4: Awaitable[_T4],
  /,
  *,
  return_exceptions: Literal[True],
) -> tuple[
  _T1 | BaseException,
  _T2 | BaseException,
  _T3 | BaseException,
  _T4 | BaseException,
]: ...
@overload
async def gather(
  coro1: Awaitable[_T1],
  coro2: Awaitable[_T2],
  coro3: Awaitable[_T3],
  coro4: Awaitable[_T4],
  coro5: Awaitable[_T5],
  /,
  *,
  return_exceptions: Literal[True],
) -> tuple[
  _T1 | BaseException,
  _T2 | BaseException,
  _T3 | BaseException,
  _T4 | BaseException,
  _T5 | BaseException,
]: ...
@overload
async def gather(
  coro1: Awaitable[_T1],
  coro2: Awaitable[_T2],
  coro3: Awaitable[_T3],
  coro4: Awaitable[_T4],
  coro5: Awaitable[_T5],
  coro6: Awaitable[_T6],
  /,
  *,
  return_exceptions: Literal[True],
) -> tuple[
  _T1 | BaseException,
  _T2 | BaseException,
  _T3 | BaseException,
  _T4 | BaseException,
  _T5 | BaseException,
  _T6 | BaseException,
]: ...
@overload
async def gather(
  *coros: Awaitable[_T],
  return_exceptions: Literal[True],
) -> tuple[_T | BaseException, ...]: ...
async def gather(  # pyright: ignore[reportInconsistentOverload]
  *coros: Awaitable[_T],
  return_exceptions: bool = False,
) -> tuple[_T, ...] | tuple[_T | BaseException, ...]:
  async def wrapper(i: int, coro: Awaitable[_T]) -> None:
    try:
      results[i] = await coro
    except BaseException as e:
      if return_exceptions:
        results[i] = e
      else:
        raise

  results: list[_T | BaseException | None] = [None for _ in coros]

  async with anyio.create_task_group() as tg:
    for i, coro in enumerate(coros):
      tg.start_soon(wrapper, i, coro)

  return cast(Any, tuple(results))


@overload
async def gather_seq(
  coros: Iterable[Awaitable[_T]],
  return_exceptions: Literal[False] = False,
) -> tuple[_T, ...]: ...
@overload
async def gather_seq(
  coros: Iterable[Awaitable[_T]],
  return_exceptions: Literal[True],
) -> tuple[_T, ...]: ...
async def gather_seq(
  coros: Iterable[Awaitable[_T]],
  return_exceptions: bool = False,
) -> tuple[_T, ...] | tuple[_T | BaseException, ...]:
  return await gather(*coros, return_exceptions=return_exceptions)


@overload
async def gather_map(
  coros: Mapping[_T1, Awaitable[_T2]],
  return_exceptions: Literal[False] = False,
) -> dict[_T1, _T2]: ...
@overload
async def gather_map(
  coros: Mapping[_T1, Awaitable[_T2]],
  return_exceptions: Literal[True],
) -> dict[_T1, _T2 | BaseException]: ...
async def gather_map(
  coros: Mapping[_T1, Awaitable[_T2]],
  return_exceptions: bool = False,
) -> dict[_T1, _T2] | dict[_T1, _T2 | BaseException]:
  async def wrapper(k: _T1, coro: Awaitable[_T2]) -> None:
    try:
      results[k] = await coro
    except BaseException as e:
      if return_exceptions:
        results[k] = e
      else:
        raise

  results: dict[_T1, _T2 | BaseException | None] = dict.fromkeys(coros)

  async with anyio.create_task_group() as tg:
    for k, coro in coros.items():
      tg.start_soon(wrapper, k, coro)

  return cast(Any, results)
