import asyncio
from typing import Optional, Union

from aiohttp import ClientSession, ClientWebSocketResponse, web
from loguru import logger

from idhagnbot.obc.v12.app import App
from idhagnbot.obc.v12.driver._common import BaseWebSocketDriver

AnyWebSocket = Union[ClientWebSocketResponse, web.WebSocketResponse]


class WebSocketRevDriver(BaseWebSocketDriver):
  def __init__(
    self,
    app: App,
    url: str,
    access_token: Optional[str] = None,
    session: Optional[ClientSession] = None,
    reconnect_interval: int = 5000,
  ) -> None:
    super().__init__(app)
    self.url = url
    if not (
      self.url.startswith("http://") or
      self.url.startswith("https://") or
      self.url.startswith("ws://") or
      self.url.startswith("wss://")
    ):
      self.url = "ws://" + self.url
    self.session = session or ClientSession()
    self.access_token = access_token
    self.reconnect_interval = reconnect_interval / 1000

  async def setup(self) -> None:
    self.__connect_task = asyncio.create_task(self.__connect())

  async def shutdown(self) -> None:
    self.__connect_task.cancel()

  async def __connect(self) -> None:
    headers = {}
    if self.access_token is not None:
      headers["Authorization"] = f"Bearer {self.access_token}"
    while True:
      try:
        async with self.session.ws_connect(self.url, headers=headers) as ws:
          logger.success(f"WebSocket server {self.url} connected.")
          await self._handle(ws)
      except Exception:
        logger.exception(f"Error when handling WebSocket connection to {self.url}")
      logger.info(f"WebSocket server {self.url} disconnected.")
      await asyncio.sleep(self.reconnect_interval)
