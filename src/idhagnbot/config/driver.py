from typing import Protocol, TextIO, TypeVar

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


class Driver(Protocol):
  @property
  def extension(self) -> str: ...
  def load(self, f: TextIO, model: type[TModel]) -> TModel: ...
  def dump(self, f: TextIO, model: BaseModel) -> None: ...
