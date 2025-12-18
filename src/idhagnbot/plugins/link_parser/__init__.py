import json
from collections.abc import Generator
from itertools import chain
from typing import Any

import cv2
import nonebot
import numpy as np
from anyio.to_thread import run_sync
from nonebot.adapters import Bot, Event
from nonebot.typing import T_State
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.asyncio import gather_seq
from idhagnbot.config import SharedConfig
from idhagnbot.context import SceneIdRaw
from idhagnbot.message import UniMsg
from idhagnbot.permission import permission
from idhagnbot.plugins.link_parser.common import Content
from idhagnbot.plugins.link_parser.contents import (
  bilibili_activity,
  bilibili_b23,
  bilibili_video,
  github,
)
from idhagnbot.url import extract_url

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_orm")
from nonebot_plugin_alconna import image_fetch
from nonebot_plugin_alconna.uniseg import Hyper, Image, Segment, Text, UniMessage
from nonebot_plugin_orm import Model, async_scoped_session


class Config(BaseModel):
  qrcode: bool = False


CONFIG = SharedConfig("link_parser", Config)
CONTENTS: list[Content] = [bilibili_activity, bilibili_b23, bilibili_video, github]


class LastState(Model):
  __tablename__ = "idhagnbot_link_parser_last_state"
  scene: Mapped[str] = mapped_column(primary_key=True)
  last_state: Mapped[str]


def extract_links(message: UniMessage[Segment]) -> Generator[str, None, None]:
  for segment in message:
    if isinstance(segment, Hyper):
      if isinstance(segment.content, dict):
        try:
          yield segment.content["meta"]["detail_1"]["qqdocurl"]
        except KeyError:
          pass
        try:
          yield segment.content["meta"]["news"]["jumpUrl"]
        except KeyError:
          pass
    elif isinstance(segment, Text):
      yield from extract_url(segment.text)


def decode(data: bytes) -> list[str]:
  im = cv2.imdecode(np.frombuffer(data, "uint8"), cv2.IMREAD_COLOR)
  if im is not None:
    _retval, decoded_info, _points, _straight_code = cv2.QRCodeDetector().detectAndDecodeMulti(im)
    return [data for data in decoded_info if data.startswith(("http://", "https://"))]
  return []


async def download_and_decode(
  bot: Bot,
  event: Event,
  state: T_State,
  image: Image,
) -> list[str]:
  data = await image_fetch(event, bot, state, image)
  return await run_sync(decode, data) if data else []


async def extract_qrcodes(
  bot: Bot,
  event: Event,
  state: T_State,
  message: UniMessage[Segment],
) -> list[str]:
  return list(
    chain.from_iterable(
      await gather_seq(download_and_decode(bot, event, state, seg) for seg in message[Image]),
    ),
  )


async def check_links(
  bot: Bot,
  event: Event,
  message: UniMsg,
  state: T_State,
  sql: async_scoped_session,
  scene: SceneIdRaw,
) -> bool:
  links = set(extract_links(message))
  if CONFIG().qrcode:
    links.update(await extract_qrcodes(bot, event, state, message))
  last = await sql.get(LastState, scene)
  last = json.loads(last.last_state) if last else dict[str, Any]()
  matched = False
  for link in links:
    results = await gather_seq(content.match_link(link, last) for content in CONTENTS)
    for content, result in zip(CONTENTS, results, strict=True):
      if result.matched:
        if matched:
          state["multiple"] = True
          return matched
        state["content"] = content
        state["state"] = result.state
        state["multiple"] = False
        matched = True
        break
  return matched


url_parser = nonebot.on_message(check_links, permission("link_parser"))


@url_parser.handle()
async def _(*, state: T_State, sql: async_scoped_session, scene: SceneIdRaw) -> None:
  result = await state["content"].format_link(**state["state"])
  current = await sql.get(LastState, scene)
  if current:
    current.last_state = json.dumps(result.state)
    sql.add(current)
  else:
    sql.add(LastState(scene=scene, last_state=json.dumps(result.state)))
  await sql.commit()
  if state["multiple"]:
    result.message += Text.br() + Text("⚠发现多个可解析链接，结果仅包含第一个")
  await result.message.send()
