from typing import TextIO, TypeVar

from pydantic import BaseModel

extension = "json"
TModel = TypeVar("TModel", bound=BaseModel)


def load(f: TextIO, model: type[TModel]) -> TModel:
  return model.model_validate_json(f.read())


def dump(f: TextIO, model: BaseModel) -> None:
  f.write(model.model_dump_json())
