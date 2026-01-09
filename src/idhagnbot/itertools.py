import sys
from collections.abc import AsyncGenerator, AsyncIterable, Generator, Iterable
from itertools import islice
from typing import NoReturn, TypeVar

__all__ = ["batched"]
T = TypeVar("T")
SimpleGenerator = Generator[T, NoReturn, None]
SimpleAsyncGenerator = AsyncGenerator[T, None]


if sys.version_info >= (3, 12):
  from itertools import batched
else:

  def batched(iterable: Iterable[T], n: int) -> SimpleGenerator[tuple[T, ...]]:
    if n < 1:
      raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
      yield batch


async def atake(iterable: AsyncIterable[T], n: int) -> SimpleAsyncGenerator[T]:
  i = 0
  async for x in iterable:
    yield x
    i += 1
    if i == n:
      break
