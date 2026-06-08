from typing import ClassVar, TextIO, TypeVar

from pydantic import BaseModel

from idhagnbot.config.driver import Driver

TModel = TypeVar("TModel", bound=BaseModel)


class JsonDriver(Driver):
  extension: ClassVar[str] = ".json"

  @staticmethod
  def load(f: TextIO, model: type[TModel]) -> TModel:
    return model.model_validate_json(f.read())

  @staticmethod
  def dump(f: TextIO, model: BaseModel) -> None:
    f.write(model.model_dump_json())
