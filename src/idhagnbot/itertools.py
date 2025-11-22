import sys
from collections.abc import Generator, Iterable
from itertools import islice, tee
from typing import NoReturn, TypeVar

__all__ = ["batched", "pairwise"]
T = TypeVar("T")
SimpleGenerator = Generator[T, NoReturn, None]


if sys.version_info >= (3, 12):
  from itertools import batched
else:

  def batched(iterable: Iterable[T], n: int) -> SimpleGenerator[tuple[T, ...]]:
    if n < 1:
      raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
      yield batch


if sys.version_info >= (3, 10):
  from itertools import pairwise
else:

  def pairwise(iterable: Iterable[T]) -> SimpleGenerator[tuple[T, T]]:
    a, b = tee(iterable)
    next(b, None)
    yield from zip(a, b)
