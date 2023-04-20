import asyncio
from typing import Optional, Set, Tuple, Union

from aiohttp import WSCloseCode, web
from loguru import logger

from idhagnbot.obc.v12.app import App
from idhagnbot.obc.v12.driver._common import BaseWebSocketDriver


def _check_request_token(token: str, request: web.Request) -> Optional[bool]:
  query = request.url.query.getall("access_token", default=[])
  header = request.headers.getall("Authorization", default=[])
  if not query and not header:
    return None
  return (query == [token] and not header) or (header == [f"Bearer {token}"] and not query)


class WebSocketDriver(BaseWebSocketDriver):
  def __init__(
    self,
    app: App,
    web_app: Union[web.Application, Tuple[str, int]],
    /,
    path: str = "/",
    access_token: Optional[str] = None
  ) -> None:
    super().__init__(app)
    if isinstance(web_app, tuple):
      self.web = web.Application()
      self.listen = web_app
    else:
      self.web = web_app
      self.listen = None
    self.path = path
    self.access_token = access_token
    self.__connections: Set[web.WebSocketResponse] = set()

  async def setup(self) -> None:
    self.web.add_routes([
      web.get(self.path, self.__connect)
    ])
    if self.listen:
      self.runner = web.AppRunner(self.web)
      await self.runner.setup()
      await web.TCPSite(self.runner, self.listen[0], self.listen[1]).start()
      logger.info(f"Websocket listening on {self.listen[0]}:{self.listen[1]}")

  async def shutdown(self) -> None:
    if self.__connections:
      await asyncio.wait([
        asyncio.create_task(ws.close(code=WSCloseCode.GOING_AWAY, message=b"Server shutdown."))
        for ws in self.__connections
      ])
    if self.listen:
      await self.runner.cleanup()

  async def __connect(self, request: web.Request) -> web.StreamResponse:
    if self.access_token is not None:
      check = _check_request_token(self.access_token, request)
      if check is None:
        return web.Response(status=401, text="No access token provided.")
      elif check is False:
        return web.Response(status=403, text="Invalid access token.")
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logger.info(f"Websocket client {request.remote} connected.")
    self.__connections.add(ws)
    try:
      await super()._handle(ws)
    finally:
      self.__connections.remove(ws)
      logger.info(f"Websocket client {request.remote} disconnected.")
    return ws
