from typing import ClassVar, TextIO, TypeVar

import yaml
from nonebot import logger
from pydantic import BaseModel

from idhagnbot.config.driver import Driver

try:
  from yaml import CSafeDumper as SafeDumper
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  logger.info("似乎没有安装libyaml，将使用纯Python的YAML解析器")
  from yaml import SafeDumper, SafeLoader

TModel = TypeVar("TModel", bound=BaseModel)


# ty 不支持模块实现 Protocol
class YamlDriver(Driver):
  extension: ClassVar[str] = ".yaml"

  @staticmethod
  def load(f: TextIO, model: type[TModel]) -> TModel:
    return model.model_validate(yaml.load(f, SafeLoader))

  @staticmethod
  def dump(f: TextIO, model: BaseModel) -> None:
    yaml.dump(model.model_dump(mode="json", by_alias=True), f, SafeDumper, allow_unicode=True)
