import asyncio
import base64
import functools
import json
import time
import uuid
from datetime import datetime
from functools import partial
from typing import Any, Union, cast

import msgpack
from aiohttp import ClientWebSocketResponse, WSMessage, WSMsgType, web
from loguru import logger
from pydantic import ValidationError
from pydantic.json import custom_pydantic_encoder, pydantic_encoder

from idhagnbot.obc.v12.action import ActionRequest, ActionResponse
from idhagnbot.obc.v12.app import App
from idhagnbot.obc.v12.driver import Driver
from idhagnbot.obc.v12.event import ConnectEvent, Event, StatusUpdateEvent

types = {
  bytes: lambda o: base64.b64encode(o).decode(),
  datetime: datetime.timestamp,
}
# https://github.com/pydantic/pydantic/issues/3768
json_encoder = partial(custom_pydantic_encoder, types)  # type: ignore


def encode_json(obj: Any) -> str:
  return json.dumps(obj, default=json_encoder)


def encode_msgpack(obj: Any) -> bytes:
  return cast(bytes, msgpack.packb(obj, default=pydantic_encoder))


AnyWebSocket = Union[ClientWebSocketResponse, web.WebSocketResponse]


class BaseWebSocketDriver(Driver):
  def __init__(self, app: App) -> None:
    super().__init__()
    self.app = app

  async def _handle(self, ws: AnyWebSocket) -> None:
    await ws.send_json(ConnectEvent(
      id=str(uuid.uuid4()),
      time=time.time(),
      type="meta",
      detail_type="connect",
      sub_type="",
      version=await self.app.get_version(),
    ), dumps=encode_json)
    await ws.send_json(StatusUpdateEvent(
      id=str(uuid.uuid4()),
      time=time.time(),
      type="meta",
      detail_type="status_update",
      sub_type="",
      status=await self.app.get_status(),
    ), dumps=encode_json)
    send_event = functools.partial(self.__send_event, ws)
    self.app.add_event_listener(send_event)
    try:
      async for msg in ws:
        if msg.type in {WSMsgType.TEXT, WSMsgType.BINARY}:
          asyncio.create_task(self.__handle_action(ws, msg))
    finally:
      self.app.remove_event_listener(send_event)

  async def __handle_action(self, ws: AnyWebSocket, msg: WSMessage) -> None:
    try:
      if msg.type == WSMsgType.BINARY:
        raw_req = msgpack.unpackb(msg.data)
      else:
        raw_req = json.loads(msg.data)
      req = ActionRequest.parse_obj(raw_req)
    except ValidationError as e:
      res = ActionResponse(
        status="failed",
        retcode=10001,
        data=None,
        message=f"Cannot parse action request: {e}",
        echo=None,
      )
    else:
      retcode, message, data = await self.app.handle_action(req.action, req.params, req.self)
      res = ActionResponse(
        status="ok" if retcode == 0 else "failed",
        retcode=retcode,
        data=data,
        message=message,
        echo=req.echo,
      )
    if msg.type == WSMsgType.BINARY:
      await ws.send_bytes(encode_msgpack(res))
    else:
      await ws.send_str(encode_json(res))

  async def __send_event(self, ws: AnyWebSocket, event: Event) -> None:
    try:
      encoded = encode_json(event)
    except Exception:
      logger.exception(f"Failed to encode event: {event}")
      return
    await ws.send_str(encoded)
