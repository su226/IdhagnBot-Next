from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

import anyio
import nonebot
from arclet.alconna._internal._util import levenshtein
from exceptiongroup import BaseExceptionGroup
from nonebot.adapters import Event
from nonebot.exception import ActionFailed
from nonebot.typing import T_State

from idhagnbot.context import get_bot_id
from idhagnbot.http import get_session
from idhagnbot.image import normalize_url
from idhagnbot.itertools import SimpleGenerator
from idhagnbot.message.common import ReplyInfo
from idhagnbot.url import path_from_url

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import (
  At,
  Image,
  Text,
  image_fetch,
)
from nonebot_plugin_uninfo import Interface, Member, SceneType, Session, User

MemeParam = Text | Image | At


@dataclass
class MemeImage:
  image: bytes
  name: str
  gender: str


async def get_member(
  interface: Interface,
  scene_type: SceneType,
  scene_id: str,
  user_id: str,
) -> Member | None:
  try:
    return await interface.get_member(scene_type, scene_id, user_id)
  except (ActionFailed, ValueError):
    return None


async def get_user(interface: Interface, user_id: str) -> User | None:
  try:
    return await interface.get_user(user_id)
  except (ActionFailed, ValueError):
    return None


async def fuzzy_get_member(
  interface: Interface,
  scene_type: SceneType,
  scene_id: str,
  criterion: str,
  threshold: float = 0.8,
) -> Member | None:
  try:
    members = await interface.get_members(scene_type, scene_id)
  except ActionFailed:
    return None
  matches = list[tuple[Member, float]]()
  for member in members:
    nick = member.nick or member.user.nick or member.user.name or member.id
    if (score := levenshtein(nick, criterion)) >= threshold:
      matches.append((member, score))
  if not matches:
    return None
  return max(matches, key=lambda x: x[1])[0]


class FetchError(ValueError):
  message: str

  def __init__(self, message: str) -> None:
    super().__init__(message)
    self.message = message


async def user_fetch(
  user_id: str,
  session: Session,
  interface: Interface,
) -> tuple[bytes, str, str]:
  if user_id == "自己":
    user_id = session.user.id
  elif user_id == "机器人":
    user_id = await get_bot_id(interface.bot)
  if member := await get_member(interface, session.scene.type, session.scene.id, user_id):
    nick = member.nick or member.user.nick or member.user.name or member.id
    gender = member.user.gender
    avatar = member.user.avatar
  elif user := await get_user(interface, user_id):
    nick = user.nick or user.name or user.id
    gender = user.gender
    avatar = user.avatar
  elif member := await fuzzy_get_member(interface, session.scene.type, session.scene.id, user_id):
    nick = member.nick or member.user.nick or member.user.name or member.id
    gender = member.user.gender
    avatar = member.user.avatar
  else:
    raise FetchError(f"找不到成员 {user_id} 或平台不支持")
  if not avatar:
    raise FetchError(f"成员 {nick} 没有头像")
  if avatar.startswith("file://"):
    async with await anyio.Path(path_from_url(avatar)).open("rb") as f:
      data = await f.read()
  else:
    async with get_session().get(normalize_url(avatar, interface.bot)) as response:
      data = await response.read()
  if gender not in ("male", "female"):
    gender = "unknown"
  return data, nick, gender


@dataclass
class FetchImage:
  image: MemeImage | None = None


async def handle_params(
  params: Iterable[MemeParam],
  reply_info: ReplyInfo | None,
  min_images: int,
  session: Session,
  interface: Interface,
  event: Event,
  state: T_State,
) -> tuple[list[str], list[MemeImage]]:
  texts: list[str] = []
  images: list[FetchImage] = []
  names: list[str] = []

  async def fetch_image_and_update(image: Image, container: FetchImage) -> None:
    if data := await image_fetch(event, interface.bot, state, image):
      container.image = MemeImage(data, "", "unknown")
    else:
      raise FetchError("无法下载图片")

  async def fetch_user_and_update(user_id: str, container: FetchImage) -> None:
    image, nick, gender = await user_fetch(user_id, session, interface)
    container.image = MemeImage(image, nick, gender)

  async with anyio.create_task_group() as tg:
    if reply_info:
      reply_images = reply_info.message[Image]
      if reply_images:
        for image in reply_images:
          container = FetchImage()
          images.append(container)
          tg.start_soon(fetch_image_and_update, image, container)
      else:
        container = FetchImage()
        images.append(container)
        tg.start_soon(fetch_user_and_update, reply_info.user_id, container)

    for param in params:
      if isinstance(param, Image):
        container = FetchImage()
        images.append(container)
        tg.start_soon(fetch_image_and_update, param, container)
      elif isinstance(param, At):
        container = FetchImage()
        images.append(container)
        tg.start_soon(fetch_user_and_update, param.target, container)
      elif param.text == "自己":
        container = FetchImage()
        images.append(container)
        tg.start_soon(fetch_user_and_update, session.user.id, container)
      elif param.text == "机器人":
        container = FetchImage()
        images.append(container)
        tg.start_soon(fetch_user_and_update, await get_bot_id(interface.bot), container)
      elif param.text.startswith("@"):
        container = FetchImage()
        images.append(container)
        tg.start_soon(fetch_user_and_update, param.text[1:], container)
      elif param.text.startswith("#"):
        names.append(param.text)
      else:
        texts.append(param.text)

    if min_images == 2:
      if len(images) == 1:
        # 当所需图片数为 2 且已指定图片数为 1 时，使用发送者的头像作为第一张图
        container = FetchImage()
        images.insert(0, container)
        tg.start_soon(fetch_user_and_update, session.user.id, container)
      elif len(images) == 0:
        # 当所需图片数为 2 且没有已指定图片时，使用发送者和机器人的头像
        container = FetchImage()
        images.append(container)
        tg.start_soon(fetch_user_and_update, session.user.id, container)
        container = FetchImage()
        images.append(container)
        tg.start_soon(fetch_user_and_update, await get_bot_id(interface.bot), container)
    elif min_images == 1 and len(images) == 0:
      # 当所需图片数为 1 且没有已指定图片时，使用发送者的头像
      container = FetchImage()
      images.append(container)
      tg.start_soon(fetch_user_and_update, session.user.id, container)

  valid_images = [image.image for image in images if image.image]
  for name, image in zip(names, valid_images, strict=False):
    image.name = name

  return texts, valid_images


def walk_exc_group(excgroup: BaseExceptionGroup) -> SimpleGenerator[BaseException]:
  for exc in excgroup.exceptions:
    if isinstance(exc, BaseExceptionGroup):
      yield from walk_exc_group(cast(BaseExceptionGroup[BaseException], exc))
    else:
      yield exc
