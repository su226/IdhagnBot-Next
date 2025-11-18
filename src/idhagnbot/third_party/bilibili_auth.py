from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

import jsonc
from pydantic import BaseModel, SecretStr, TypeAdapter
from typing_extensions import NotRequired, TypedDict

from idhagnbot.config import SharedConfig


class Config(BaseModel):
  cookie_type: Literal["static", "bilibilitool"] = "static"
  cookie: SecretStr = SecretStr("")
  bilibilitool_cookies_file: Path = Path()
  bilibilitool_cookies_index: int = 0


CONFIG = SharedConfig("bilibili_auth", Config)
TData = TypeVar("TData")


def get_cookie() -> str:
  config = CONFIG()
  if config.cookie_type == "static":
    return config.cookie.get_secret_value()
  with config.bilibilitool_cookies_file.open() as f:
    data = jsonc.load(f)
  return data["BiliBiliCookies"][config.bilibilitool_cookies_index]


class ApiResult(TypedDict, Generic[TData]):
  code: int
  message: str
  ttl: int
  data: NotRequired[TData]


class ApiError(Exception):
  def __init__(self, code: int, message: str) -> None:
    super().__init__(f"{code}: {message}")
    self.code = code
    self.message = message

  def __repr__(self) -> str:
    return f"ApiError(code={self.code!r}, message={self.message!r})"


def validate_result(result: dict[str, Any], data_type: type[TData]) -> TData:
  parsed = TypeAdapter(ApiResult[data_type], config={"strict": True}).validate_python(result)
  if "data" not in parsed:
    raise ApiError(parsed["code"], parsed["message"])
  return parsed["data"]
