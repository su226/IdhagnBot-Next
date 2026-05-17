import nonebot
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from nonebot import logger

from idhagnbot.webui.common import CONFIG

__all__ = ["FastAPI", "setup"]


def setup(app: FastAPI) -> None:
  config = CONFIG()
  static_path = config.static_path
  if static_path is None:
    return

  async def catch_all(request: Request, exception: Exception) -> FileResponse:
    return FileResponse(static_path / "index.html")

  async def redirect() -> RedirectResponse:
    return RedirectResponse("/idhagnbot-webui", 301)

  sub = FastAPI()
  sub.mount("/", StaticFiles(directory=static_path, html=True))
  sub.exception_handler(404)(catch_all)
  app.mount("/idhagnbot-webui", sub)
  if config.redirect:
    app.get("/")(redirect)
    path = ""
  else:
    path = "idhagnbot-webui"

  driver = nonebot.get_driver()
  host = driver.config.host
  port = driver.config.port
  url = f"http://{host}/{path}" if port == 80 else f"http://{host}:{port}/{path}"

  async def print_log() -> None:
    logger.success(f"IdhagnBot WebUI 已在 {url} 可用。")

  nonebot.get_driver().on_startup(print_log)
