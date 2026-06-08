import nonebot
from nonebot.drivers import ASGIMixin, HTTPServerSetup, Request, Response
from pydantic import BaseModel
from yarl import URL

from idhagnbot.webui.common import ResponseData, authenticate
from idhagnbot.webui.config import setup as setup_config_editor
from idhagnbot.webui.dashboard import setup as setup_dashboard

try:
  from idhagnbot.webui import static_fastapi
except ImportError:
  static_fastapi: None = None


class AuthenticateResponseData(BaseModel):
  plugins: set[str]


async def handle_authenticate(request: Request) -> Response:
  if response := authenticate(request):
    return response
  return ResponseData.res_success(
    AuthenticateResponseData(plugins={plugin.id_ for plugin in nonebot.get_loaded_plugins()}),
  )


def setup(driver: ASGIMixin) -> None:
  driver.setup_http_server(
    HTTPServerSetup(
      URL("/idhagnbot-api/authenticate"),
      "POST",
      "IdhagnBot Authenticate",
      handle_authenticate,
    ),
  )
  if static_fastapi and isinstance(driver.server_app, static_fastapi.FastAPI):
    static_fastapi.setup(driver.server_app)
  setup_config_editor(driver)
  setup_dashboard(driver)


if isinstance(driver := nonebot.get_driver(), ASGIMixin):
  setup(driver)
