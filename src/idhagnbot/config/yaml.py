from typing import ClassVar, TextIO, TypeVar

from nonebot import logger
from pydantic import BaseModel
from ruamel.yaml import YAML, CParser

from idhagnbot.config.driver import Driver

if CParser is None:
  logger.info("似乎没有安装 ruamel.yaml.clib 或 ruamel.yaml.clibz，将使用纯 Python 的 YAML 解析器")
yaml = YAML(typ="safe")  # 暂无计划支持 Round-Trip 和图形化的配置编辑器。
yaml.allow_unicode = True
TModel = TypeVar("TModel", bound=BaseModel)


# ty 不支持模块实现 Protocol
class YamlDriver(Driver):
  extension: ClassVar[str] = ".yaml"

  @staticmethod
  def load(f: TextIO, model: type[TModel]) -> TModel:
    return model.model_validate(yaml.load(f))

  @staticmethod
  def dump(f: TextIO, model: BaseModel) -> None:
    yaml.dump(model.model_dump(mode="json", by_alias=True), f)
