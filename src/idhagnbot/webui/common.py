from hmac import compare_digest
from pathlib import Path
from typing import override

from arclet.entari import metadata, plugin_config
from entari_plugin_server import get_asgi
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, SecretStr
from starlette.applications import Starlette


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
    WebUI 前端文件的路径，将被挂载到 http://<HOST>:<PORT>/idhagnbot
    仅支持 FastAPI 驱动器，该配置项不可热重载。设置为 null 时将不会自动挂载。
    可选，默认：null
    """

    redirect: bool = True
    """
    是否将 / 301 重定向到 /idhagnbot。如果与其他插件冲突，将此选项设置为 false。
    可选，默认：true
    """


def setup_static(app: Starlette, path: Path) -> None:
    async def catch_all(request: Request, exception: Exception) -> FileResponse:
        return FileResponse(path / "index.html")

    sub = Starlette()
    sub.mount("/", StaticFiles(directory=path, html=True))
    sub.add_exception_handler(404, catch_all)
    app.mount("/idhagnbot", sub)


def setup_redirect(app: Starlette) -> None:
    async def redirect(request: Request) -> RedirectResponse:
        return RedirectResponse("/idhagnbot", 301)

    app.add_route("/", redirect)


metadata("", config=Config)
CONFIG = plugin_config(Config)
APP = FastAPI()
parent: Starlette = get_asgi()
parent.mount("/idhagnbot-api", APP)
if CONFIG.static_path:
    setup_static(parent, CONFIG.static_path)
    if CONFIG.redirect:
        setup_redirect(parent)


class ResponseData[T](BaseModel):
    code: str
    message: str
    data: T

    @classmethod
    def res_success(cls, data: T) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=cls(code="success", message="", data=data).model_dump(mode="json"),
        )

    @classmethod
    def res_error(
        cls: type[ResponseData[None]],
        status: int,
        code: str,
        message: str,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content=cls(code=code, message=message, data=None).model_dump(mode="json"),
        )


class WebUIException(Exception):
    def __init__(self) -> None:
        pass

    def get_status(self) -> int:
        return 500

    def get_code(self) -> str:
        return "internal_error"

    def get_message(self) -> str:
        return "内部错误"


class WebUINotEnabled(WebUIException):
    @override
    def get_status(self) -> int:
        return 503

    @override
    def get_code(self) -> str:
        return "webui_not_enabled"

    @override
    def get_message(self) -> str:
        return "WebUI 未启用"


class InvalidToken(WebUIException):
    @override
    def get_status(self) -> int:
        return 403

    @override
    def get_code(self) -> str:
        return "invalid_token"

    @override
    def get_message(self) -> str:
        return "Token 无效"


@APP.exception_handler(WebUIException)
async def handle_webui_exception(
    request: Request,
    exception: WebUIException,
) -> JSONResponse:
    return ResponseData.res_error(
        exception.get_status(),
        exception.get_code(),
        exception.get_message(),
    )


def authorize(request: Request) -> None:
    token = CONFIG.token
    if token is None:
        raise WebUINotEnabled
    input_token = request.headers.get("Authorization", "")
    if not input_token.startswith("Bearer "):
        raise InvalidToken
    input_token = input_token[7:]
    if not compare_digest(input_token, token.get_secret_value()):
        raise InvalidToken
