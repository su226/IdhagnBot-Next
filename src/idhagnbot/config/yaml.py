from typing import TextIO, TypeVar

import yaml
from nonebot import logger
from pydantic import BaseModel

try:
  from yaml import CSafeDumper as SafeDumper
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  logger.info("似乎没有安装libyaml，将使用纯Python的YAML解析器")
  from yaml import SafeDumper, SafeLoader

extension = "yaml"
TModel = TypeVar("TModel", bound=BaseModel)


def load(f: TextIO, model: type[TModel]) -> TModel:
  return model.model_validate(yaml.load(f, SafeLoader))


def dump(f: TextIO, model: BaseModel) -> None:
  yaml.dump(model.model_dump(mode="json", by_alias=True), f, SafeDumper, allow_unicode=True)
