import abc
from types import TracebackType
from typing import Optional, Type

from typing_extensions import Self


class Driver(abc.ABC):
  @abc.abstractmethod
  async def setup(self) -> None: ...

  async def __aenter__(self) -> Self:
    await self.setup()
    return self

  @abc.abstractmethod
  async def shutdown(self) -> None: ...

  async def __aexit__(
    self,
    exctype: Optional[Type[BaseException]],
    exc: Optional[BaseException],
    tb: Optional[TracebackType]
  ) -> Optional[bool]:
    await self.shutdown()
