from hmac import compare_digest
from pathlib import Path
from typing import Generic, TypeVar

from nonebot.drivers import Request, Response
from pydantic import BaseModel, SecretStr

from idhagnbot.config import SharedConfig


class Config(BaseModel, use_attribute_docstrings=True):
  """
  WebUI 相关配置
  """

  token: SecretStr | None = None
  """
  WebUI 的令牌，设置为 null 以禁用 WebUI。出于安全性考虑，不建议设置为空字符串。
  令牌明文传输，如果需要将 WebUI 暴露于公网，请使用 Nginx 等配置 HTTPS 反代。
  可选，默认：null
  """

  static_path: Path | None = None
  """
  WebUI 前端文件的路径，将被挂载到 http://<HOST>:<PORT>/idhagnbot-webui
  仅支持 FastAPI 驱动器，该配置项不可热重载。设置为 null 时将不会自动挂载。
  可选，默认：null
  """

  redirect: bool = True
  """
  是否将 / 301 重定向到 /idhagnbot-webui。如果与其他插件冲突，将此选项设置为 false。
  可选，默认：true
  """


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
