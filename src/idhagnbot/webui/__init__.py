import nonebot
from nonebot.drivers import ASGIMixin, HTTPServerSetup, Request, Response
from pydantic import BaseModel
from yarl import URL

from idhagnbot.webui.common import ResponseData, authenticate
from idhagnbot.webui.config import setup as setup_config_editor


class AuthenticateResponseData(BaseModel):
  plugins: set[str]


async def handle_authenticate(request: Request) -> Response:
  if response := authenticate(request):
    return response
  return Response(
    200,
    content=ResponseData(
      success=True,
      message="",
      data=AuthenticateResponseData(
        plugins={plugin.id_ for plugin in nonebot.get_loaded_plugins()},
      ),
    ).model_dump_json(),
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
  setup_config_editor(driver)


if isinstance(driver := nonebot.get_driver(), ASGIMixin):
  setup(driver)
