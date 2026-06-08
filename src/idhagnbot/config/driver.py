from typing import Protocol, TextIO, TypeVar

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


class Driver(Protocol):
  @property
  def extension(self) -> str: ...
  @staticmethod
  def load(f: TextIO, model: type[TModel]) -> TModel: ...
  @staticmethod
  def dump(f: TextIO, model: BaseModel) -> None: ...
