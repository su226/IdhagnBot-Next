from collections.abc import Callable
from enum import Enum, auto
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, Generic, TypeVar

import nonebot
from nonebot import logger
from pydantic import BaseModel

from idhagnbot.config.driver import Driver
from idhagnbot.config.json import JsonDriver
from idhagnbot.config.yaml import YamlDriver

nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_cache_dir, get_config_dir, get_data_dir

TModel = TypeVar("TModel", bound=BaseModel)
SharedLoaderCallback = Callable[[TModel | None, TModel], None]
CONFIG_DIR = get_config_dir("idhagnbot")
DATA_DIR = get_data_dir("idhagnbot")
CACHE_DIR = get_cache_dir("idhagnbot")


class Reloadable(Enum):
  FALSE = auto()
  EAGER = auto()
  LAZY = auto()


class SharedLoader(Generic[TModel]):
  __slots__ = (
    "__cache",
    "__callbacks",
    "__category",
    "__driver",
    "__lock",
    "__model",
    "__path",
    "__reloadable",
  )

  def __init__(
    self,
    category: str,
    path: Path,
    driver: Driver,
    model: type[TModel],
    reloadable: Reloadable,
  ) -> None:
    self.__category = category
    self.__path = path
    self.__driver = driver
    self.__model = model
    self.__lock = Lock()
    self.__reloadable = reloadable
    self.__cache: TModel | None = None
    self.__callbacks = list[Callable[[TModel | None, TModel], None]]()

  @property
  def path(self) -> Path:
    return self.__path

  @property
  def model(self) -> type[TModel]:
    return self.__model

  @property
  def reloadable(self) -> Reloadable:
    return self.__reloadable

  def __call__(self) -> TModel:
    if self.__cache is None:
      with self.__lock:  # Nonebot 的 run_sync 不在主线程
        if self.__cache is None:
          return self.__load()
    return self.__cache

  def __load(self) -> TModel:
    path = self.__path.with_suffix(self.__driver.extension)
    if path.exists():
      logger.info(f"加载{self.__category}文件: {path}")
      with path.open() as f:
        new_config = self.__driver.load(f, self.__model)
    else:
      logger.info(f"{self.__category}文件不存在: {path}")
      new_config = self.__model()
    old_config = self.__cache
    self.__cache = new_config
    for callback in self.__callbacks:
      callback(old_config, new_config)
    return new_config

  def dump(self) -> None:
    path = self.__path.with_suffix(self.__driver.extension)
    if self.__cache is None:
      logger.info(f"{self.__category}数据未加载: {path}")
      return
    logger.info(f"保存{self.__category}文件: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
      self.__driver.dump(f, self.__cache)

  def onload(self, func: SharedLoaderCallback[TModel]) -> SharedLoaderCallback[TModel]:
    self.__callbacks.append(func)
    return func

  def reload(self) -> None:
    if self.__reloadable is Reloadable.FALSE:
      raise ValueError(f"{self} 不可重载")
    with self.__lock:
      if self.__reloadable is Reloadable.EAGER:
        self.__load()
      else:
        self.__cache = None


class SharedConfig(Generic[TModel]):
  all: ClassVar[dict[str, "SharedConfig[Any]"]] = {}
  __slots__ = ("__loader",)

  def __init__(
    self,
    name: str,
    model: type[TModel],
    reloadable: Reloadable = Reloadable.LAZY,
  ) -> None:
    self.__loader = SharedLoader("配置", CONFIG_DIR / name, YamlDriver, model, reloadable)
    self.all[name] = self

  @property
  def name(self) -> str:
    return self.__loader.path.stem

  @property
  def model(self) -> type[TModel]:
    return self.__loader.model

  @property
  def reloadable(self) -> Reloadable:
    return self.__loader.reloadable

  def __call__(self) -> TModel:
    return self.__loader()

  def reload(self) -> None:
    self.__loader.reload()

  def onload(self, func: SharedLoaderCallback[TModel]) -> SharedLoaderCallback[TModel]:
    return self.__loader.onload(func)


class SharedData(Generic[TModel]):
  all: ClassVar[dict[str, "SharedData[Any]"]] = {}
  __slots__ = ("__loader",)

  def __init__(
    self,
    name: str,
    model: type[TModel],
    reloadable: Reloadable = Reloadable.LAZY,
  ) -> None:
    self.__loader = SharedLoader("数据", DATA_DIR / name, JsonDriver, model, reloadable)
    self.all[name] = self

  @property
  def name(self) -> str:
    return self.__loader.path.stem

  @property
  def model(self) -> type[TModel]:
    return self.__loader.model

  @property
  def reloadable(self) -> Reloadable:
    return self.__loader.reloadable

  def __call__(self) -> TModel:
    return self.__loader()

  def dump(self) -> None:
    self.__loader.dump()

  def reload(self) -> None:
    self.__loader.reload()

  def onload(self, func: SharedLoaderCallback[TModel]) -> SharedLoaderCallback[TModel]:
    return self.__loader.onload(func)


class SharedCache(Generic[TModel]):
  all: ClassVar[dict[str, "SharedCache[Any]"]] = {}
  __slots__ = ("__loader",)

  def __init__(
    self,
    name: str,
    model: type[TModel],
    reloadable: Reloadable = Reloadable.LAZY,
  ) -> None:
    self.__loader = SharedLoader("缓存", DATA_DIR / name, JsonDriver, model, reloadable)
    self.all[name] = self

  @property
  def name(self) -> str:
    return self.__loader.path.stem

  @property
  def model(self) -> type[TModel]:
    return self.__loader.model

  @property
  def reloadable(self) -> Reloadable:
    return self.__loader.reloadable

  def __call__(self) -> TModel:
    return self.__loader()

  def dump(self) -> None:
    self.__loader.dump()

  def reload(self) -> None:
    self.__loader.reload()

  def onload(self, func: SharedLoaderCallback[TModel]) -> SharedLoaderCallback[TModel]:
    return self.__loader.onload(func)
