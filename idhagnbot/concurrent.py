import asyncio
import contextvars
import functools
import sys
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Coroutine, Optional, TypeVar, cast

from typing_extensions import ParamSpec

__all__ = "to_thread", "io_bound", "to_process", "cpu_bound"
_P = ParamSpec("_P")
_R = TypeVar("_R")
_process_executor: Optional[ProcessPoolExecutor] = None


if sys.version_info >= (3, 9):
  to_thread = asyncio.to_thread
else:
  async def to_thread(func: Callable[_P, _R], /, *args: _P.args, **kwargs: _P.kwargs) -> _R:
    """Polyfill for asyncio.to_thread"""
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    func_call = functools.partial(ctx.run, func, *args, **kwargs)
    return cast(_R, await loop.run_in_executor(None, func_call))


def io_bound(func: Callable[_P, _R]) -> Callable[_P, Coroutine[Any, Any, _R]]:
  return cast(Any, functools.partial(to_thread, func))


async def to_process(func: Callable[_P, _R], /, *args: _P.args, **kwargs: _P.kwargs) -> _R:
  """Process version of asyncio.to_thread"""
  loop = asyncio.get_running_loop()
  ctx = contextvars.copy_context()
  global _process_executor
  if _process_executor is None:
    _process_executor = ProcessPoolExecutor()
  func_call = functools.partial(ctx.run, func, *args, **kwargs)
  return cast(_R, await loop.run_in_executor(_process_executor, func_call))


def cpu_bound(func: Callable[_P, _R]) -> Callable[_P, Coroutine[Any, Any, _R]]:
  return cast(Any, functools.partial(to_process, func))
