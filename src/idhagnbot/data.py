from collections.abc import Callable
from enum import Enum, auto
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, Protocol, TextIO

from arclet.entari import local_data
from loguru import logger
from pydantic import BaseModel


class Driver(Protocol):
    @property
    def extension(self) -> str: ...
    @staticmethod
    def load[TModel: BaseModel](f: TextIO, model: type[TModel]) -> TModel: ...
    @staticmethod
    def dump(f: TextIO, model: BaseModel) -> None: ...


class Json(Driver):
    extension = ".json"

    @staticmethod
    def load[TModel: BaseModel](f: TextIO, model: type[TModel]) -> TModel:
        return model.model_validate_json(f.read())

    @staticmethod
    def dump(f: TextIO, model: BaseModel) -> None:
        f.write(model.model_dump_json())


type SharedLoaderCallback[TModel: BaseModel] = Callable[[TModel | None, TModel], None]
DATA_DIR = local_data.get_data_dir("idhagnbot")
CACHE_DIR = local_data.get_cache_dir("idhagnbot")


class Reloadable(Enum):
    FALSE = auto()
    EAGER = auto()
    LAZY = auto()


class SharedLoader[TModel: BaseModel]:
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

    def onload(
        self,
        func: SharedLoaderCallback[TModel],
    ) -> SharedLoaderCallback[TModel]:
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


class SharedData[TModel: BaseModel]:
    all: ClassVar[dict[str, SharedData[Any]]] = {}
    __slots__ = ("__loader",)

    def __init__(
        self,
        name: str,
        model: type[TModel],
        reloadable: Reloadable = Reloadable.LAZY,
    ) -> None:
        self.__loader = SharedLoader("数据", DATA_DIR / name, Json, model, reloadable)
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

    def onload(
        self,
        func: SharedLoaderCallback[TModel],
    ) -> SharedLoaderCallback[TModel]:
        return self.__loader.onload(func)


class SharedCache[TModel: BaseModel]:
    all: ClassVar[dict[str, SharedCache[Any]]] = {}
    __slots__ = ("__loader",)

    def __init__(
        self,
        name: str,
        model: type[TModel],
        reloadable: Reloadable = Reloadable.LAZY,
    ) -> None:
        self.__loader = SharedLoader("缓存", CACHE_DIR / name, Json, model, reloadable)
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

    def onload(
        self,
        func: SharedLoaderCallback[TModel],
    ) -> SharedLoaderCallback[TModel]:
        return self.__loader.onload(func)
