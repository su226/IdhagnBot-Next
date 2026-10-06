import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable, Mapping
from datetime import datetime, timedelta
from inspect import iscoroutine
from typing import Any

from loguru import logger

type BackgroundExceptionHandler = Callable[[BaseException, str, str], Awaitable[None]]
type HandlerFn = Callable[[], Awaitable[Any]]
type DisposeFn = Callable[[], None]
_background_tasks: set[asyncio.Task[None]] = set()
_background_exception_handlers: set[BackgroundExceptionHandler] = set()


async def _coroutine_wrapper[T](coro: Awaitable[T]) -> T:
    return await coro


def ensure_coroutine[T](coro: Awaitable[T]) -> Coroutine[Any, Any, T]:
    if iscoroutine(coro):
        return coro
    return _coroutine_wrapper(coro)


async def _call_background_exception_handler(
    e: BaseException,
    module: str,
    name: str,
) -> None:
    logger.exception("后台任务出错")
    try:
        async with asyncio.TaskGroup() as tg:
            for handler in _background_exception_handlers:
                tg.create_task(ensure_coroutine(handler(e, module, name)))
    except asyncio.CancelledError:
        pass
    except BaseException:
        logger.exception("运行后台任务错误回调时出错")


async def _background_task_wrapper(coro: Awaitable[None]) -> None:
    try:
        await coro
    except asyncio.CancelledError:
        pass
    except BaseException as e:
        module = getattr(coro, "__module__", "<unknown>")
        name = getattr(coro, "__name__", "<unknown>")
        await _call_background_exception_handler(e, module, name)


def create_background_task(
    coro: Awaitable[None],
    label: str | None = None,
) -> DisposeFn:
    task = asyncio.create_task(_background_task_wrapper(coro))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    def dispose() -> None:
        task.cancel()
        _background_tasks.discard(task)

    return dispose


def delayed(
    delay: datetime | timedelta,
    label: str | None = None,
) -> Callable[[HandlerFn], DisposeFn]:
    def wrapper(fn: HandlerFn) -> DisposeFn:
        async def do_execute() -> None:
            try:
                await fn()
            except asyncio.CancelledError:
                pass
            except BaseException as e:
                module = getattr(fn, "__module__", "<unknown>")
                name = getattr(fn, "__name__", "<unknown>")
                await _call_background_exception_handler(e, module, name)

        def execute() -> None:
            nonlocal current_task
            current_task = asyncio.create_task(do_execute())

        loop = asyncio.get_running_loop()
        current_task: asyncio.Task[None] | None = None
        if isinstance(delay, timedelta):
            current_timer = loop.call_later(delay.total_seconds(), execute)
        else:
            current_timer = loop.call_at(delay.timestamp(), execute)

        def dispose() -> None:
            nonlocal current_timer, current_task
            current_timer.cancel()
            if current_task:
                current_task.cancel()

        return dispose

    return wrapper


def delayed_loop(
    delay: timedelta,
    immediate: bool = False,
    label: str | None = None,
) -> Callable[[HandlerFn], DisposeFn]:
    """
    执行完成等待一段时间间隔后再次执行，比如一个函数执行 5 秒，间隔 10 秒，
    周期就是 15 秒 而非 10 秒。
    """
    seconds = delay.total_seconds()

    def wrapper(fn: HandlerFn) -> DisposeFn:
        async def do_execute() -> None:
            cancelled = False
            try:
                await fn()
            except asyncio.CancelledError:
                cancelled = True
            except BaseException as e:
                module = fn.__module__
                name = getattr(fn, "__name__", "<unknown>")
                await _call_background_exception_handler(e, module, name)
            finally:
                if not cancelled:
                    nonlocal current_timer
                    current_timer = loop.call_later(seconds, execute)

        def execute() -> None:
            nonlocal current_task
            current_task = asyncio.create_task(do_execute())

        loop = asyncio.get_running_loop()
        if immediate:
            current_timer = None
            current_task = asyncio.create_task(do_execute())
        else:
            current_timer = loop.call_later(seconds, execute)
            current_task = None

        def dispose() -> None:
            nonlocal current_timer, current_task
            if current_timer:
                current_timer.cancel()
            if current_task:
                current_task.cancel()

        return dispose

    return wrapper


def background_exception_handler(
    func: BackgroundExceptionHandler,
) -> Callable[[], None]:
    _background_exception_handlers.add(func)
    return lambda: _background_exception_handlers.discard(func)


def gather_seq[T](coros: Iterable[Awaitable[T]]) -> asyncio.Future[list[T]]:
    return asyncio.gather(*coros)


async def gather_map[K, V](coros: Mapping[K, Awaitable[V]]) -> dict[K, V]:
    async with asyncio.TaskGroup() as tg:
        tasks = {k: tg.create_task(ensure_coroutine(v)) for k, v in coros.items()}
    return {k: v.result() for k, v in tasks.items()}
