import sys
from collections.abc import Generator, Iterable
from itertools import islice
from typing import NoReturn, TypeVar

__all__ = ["batched"]
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
