from hmac import compare_digest
from typing import Generic, TypeVar

from nonebot.drivers import Request, Response
from pydantic import BaseModel, SecretStr

from idhagnbot.config import SharedConfig


class Config(BaseModel):
  token: SecretStr | None = None


CONFIG = SharedConfig("webui", Config)
T = TypeVar("T")


class ResponseData(BaseModel, Generic[T]):
  success: bool
  message: str
  data: T


def authenticate(request: Request) -> Response | None:
  token = CONFIG().token
  if token is None:
    return Response(
      503,
      content=ResponseData(success=False, message="WebUI 未启用", data=None).model_dump_json(),
    )
  input_token = request.headers.get("Authorization", "")
  if not input_token.startswith("Bearer "):
    return Response(
      403,
      content=ResponseData(success=False, message="Token 无效", data=None).model_dump_json(),
    )
  input_token = input_token[7:]
  if not compare_digest(input_token, token.get_secret_value()):
    return Response(
      403,
      content=ResponseData(success=False, message="Token 无效", data=None).model_dump_json(),
    )
  return None
