import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, Generic, Literal, TypeVar

import nonebot
import yaml
from nonebot import logger
from pydantic import BaseModel
from typing_extensions import TypeVarTuple, Unpack, override

try:
  from yaml import CSafeDumper as SafeDumper
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  logger.info("似乎没有安装libyaml，将使用纯Python的YAML解析器")
  from yaml import SafeDumper, SafeLoader

nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_cache_dir, get_config_dir, get_data_dir

TModel = TypeVar("TModel", bound=BaseModel)
TParam = TypeVarTuple("TParam")
LoadHandler = Callable[[TModel | None, TModel, Unpack[TParam]], None]
Reloadable = Literal[False, "eager", "lazy"]
CONFIG_DIR = get_config_dir("idhagnbot")
DATA_DIR = get_data_dir("idhagnbot")
CACHE_DIR = get_cache_dir("idhagnbot")
GROUP_ID_RE = re.compile(r"^(?P<platform>.+)__group__(?P<group>.+)$")
GROUP_RE = re.compile(r"^(?P<platform>.+)__group$")
PRIVATE_ID_RE = re.compile(r"^(?P<platform>.+)__private__(?P<user>.+)$")
PRIVATE_RE = re.compile(r"^(?P<platform>.+)__private$")


@dataclass
class CacheItem(Generic[TModel]):
  item: TModel
  need_reload: bool = False


class BaseConfig(Generic[TModel, Unpack[TParam]]):
  category: ClassVar[str] = "配置"
  all: ClassVar[list["BaseConfig[Any, Unpack[tuple[Any, ...]]]"]] = []

  model: type[TModel]
  cache: dict[tuple[Unpack[TParam]], CacheItem[TModel]]
  reloadable: Reloadable
  handlers: list[LoadHandler[TModel, Unpack[TParam]]]
  lock: Lock

  def __init__(self, model: type[TModel], reloadable: Reloadable = "lazy") -> None:
    super().__init__()
    self.model = model
    self.cache = {}
    self.reloadable = reloadable
    self.handlers = []
    self.lock = Lock()
    self.all.append(self)

  def get_file(self, *args: Unpack[TParam]) -> Path:
    raise NotImplementedError

  def __call__(self, *args: Unpack[TParam]) -> TModel:
    if args not in self.cache or self.cache[args].need_reload:
      with self.lock:  # Nonebot 的 run_sync 不在主线程
        if args not in self.cache or self.cache[args].need_reload:
          self.load(*args)
    return self.cache[args].item

  def load(self, *args: Unpack[TParam]) -> None:
    file = self.get_file(*args)
    if file.exists():
      logger.info(f"加载{self.category}文件: {file}")
      with file.open() as f:
        new_config = self.model.model_validate(yaml.load(f, SafeLoader))
    else:
      logger.info(f"{self.category}文件不存在: {file}")
      new_config = self.model()
    if args not in self.cache:
      old_config = None
      self.cache[args] = CacheItem(new_config)
    else:
      cache_item = self.cache[args]
      old_config = cache_item.item
      cache_item.item = new_config
      cache_item.need_reload = False
    for handler in self.handlers:
      handler(old_config, new_config, *args)

  def dump(self, *args: Unpack[TParam]) -> None:
    if args not in self.cache:
      return
    data = self.cache[args].item.model_dump(mode="json", by_alias=True)
    file = self.get_file(*args)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w") as f:
      yaml.dump(data, f, SafeDumper, allow_unicode=True)

  def onload(
    self,
  ) -> Callable[[LoadHandler[TModel, Unpack[TParam]]], LoadHandler[TModel, Unpack[TParam]]]:
    def decorator(
      handler: LoadHandler[TModel, Unpack[TParam]],
    ) -> LoadHandler[TModel, Unpack[TParam]]:
      self.handlers.append(handler)
      return handler

    return decorator

  def reload(self) -> None:
    if self.reloadable == "eager":
      for key in self.cache:
        self.load(*key)
    elif self.reloadable == "lazy":
      for v in self.cache.values():
        v.need_reload = True
    else:
      raise ValueError(f"{self} 不可重载")


class SharedConfig(BaseConfig[TModel]):
  base_dir: ClassVar[Path] = CONFIG_DIR

  name: str

  def __init__(self, name: str, model: type[TModel], reloadable: Reloadable = "lazy") -> None:
    super().__init__(model, reloadable)
    self.name = name

  @override
  def get_file(self) -> Path:
    return self.base_dir / f"{self.name}.yaml"


class SharedData(SharedConfig[TModel]):
  category: ClassVar[str] = "数据"
  base_dir: ClassVar[Path] = DATA_DIR


class SharedCache(SharedConfig[TModel]):
  category: ClassVar[str] = "缓存"
  base_dir: ClassVar[Path] = CACHE_DIR


class SessionConfig(BaseConfig[TModel, str]):
  base_dir: ClassVar[Path] = CONFIG_DIR

  name: str

  def __init__(self, name: str, model: type[TModel], reloadable: Reloadable = "lazy") -> None:
    super().__init__(model, reloadable)
    self.name = name

  @override
  def get_file(self, session: str) -> Path:
    file = self.base_dir / self.name / f"{session}.yaml"
    if not file.exists():
      fallback = self._get_fallback(session)
      while fallback:
        fallback_file = self.base_dir / self.name / f"{fallback}.yaml"
        if fallback_file.exists():
          return fallback_file
        fallback = self._get_fallback(session)
    return file

  def _get_fallback(self, name: str) -> str | None:
    if match := GROUP_ID_RE.match(name):
      return f"{match['platform']}__group"
    if match := GROUP_RE.match(name):
      return match["platform"]
    if match := PRIVATE_ID_RE.match(name):
      return f"{match['platform']}__private"
    if match := PRIVATE_RE.match(name):
      return match["platform"]
    if name == "default":
      return None
    return "default"


class SessionData(SessionConfig[TModel]):
  category: ClassVar[str] = "数据"
  base_dir: ClassVar[Path] = DATA_DIR


class SessionCache(SessionConfig[TModel]):
  category: ClassVar[str] = "缓存"
  base_dir: ClassVar[Path] = CACHE_DIR
