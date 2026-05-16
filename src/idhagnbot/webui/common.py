from hmac import compare_digest
from pathlib import Path
from typing import Generic, TypeVar

from nonebot.drivers import Request, Response
from pydantic import BaseModel, SecretStr

from idhagnbot.config import SharedConfig


class Config(BaseModel):
  token: SecretStr | None = None
  static_path: Path | None = None
  redirect: bool = True


CONFIG = SharedConfig("webui", Config)
T = TypeVar("T")


class ResponseData(BaseModel, Generic[T]):
  success: bool
  message: str
  data: T

  @classmethod
  def res_success(cls, data: T) -> Response:
    return Response(200, content=cls(success=True, message="", data=data).model_dump_json())

  @classmethod
  def res_error(cls: type["ResponseData[None]"], code: int, message: str) -> Response:
    return Response(code, content=cls(success=False, message=message, data=None).model_dump_json())


def authenticate(request: Request) -> Response | None:
  token = CONFIG().token
  if token is None:
    return ResponseData.res_error(503, "WebUI 未启用")
  input_token = request.headers.get("Authorization", "")
  if not input_token.startswith("Bearer "):
    return ResponseData.res_error(403, "Token 无效")
  input_token = input_token[7:]
  if not compare_digest(input_token, token.get_secret_value()):
    return ResponseData.res_error(403, "Token 无效")
  return None
