from collections.abc import AsyncGenerator, AsyncIterable

__all__ = ["atake"]


async def atake[T](iterable: AsyncIterable[T], n: int) -> AsyncGenerator[T]:
    i = 0
    async for x in iterable:
        yield x
        i += 1
        if i >= n:
            break
