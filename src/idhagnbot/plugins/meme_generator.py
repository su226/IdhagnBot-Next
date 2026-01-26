import json
import random
from datetime import datetime
from typing import Any

import anyio
import nonebot
from aiohttp import ClientError, FormData
from arclet.alconna import ArgFlag, Args, Empty, Option
from arclet.alconna.action import Action
from exceptiongroup import BaseExceptionGroup
from nonebot import logger
from nonebot.adapters import Event
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot.utils import flatten_exception_group
from pydantic import BaseModel, HttpUrl, TypeAdapter

from idhagnbot.asyncio import create_background_task
from idhagnbot.command import CommandBuilder
from idhagnbot.config import SharedConfig
from idhagnbot.http import get_session
from idhagnbot.meme_common import FetchError, MemeImage, MemeParam, handle_params
from idhagnbot.message import send_image_or_animation
from idhagnbot.message.common import MaybeReplyInfo

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, Arparma, CommandMeta, Image, MultiVar, UniMessage
from nonebot_plugin_uninfo import QryItrface, Uninfo


class Config(BaseModel):
  base_url: HttpUrl | None = None


class ParserArg(BaseModel):
  name: str
  value: str
  default: Any | None = None
  flags: list[ArgFlag] | None = None


class ParserOption(BaseModel):
  names: list[str]
  args: list[ParserArg] | None = None
  dest: str | None = None
  default: Any | None = None
  action: Action | None = None
  help_text: str | None = None
  compact: bool = False

  def option(self) -> Option:
    args = Args()
    for arg in self.args or []:
      args.add(
        name=arg.name,
        value=arg.value,
        default=arg.default or Empty,
        flags=arg.flags,
      )

    return Option(
      name="|".join(self.names),
      args=args,
      dest=self.dest,
      default=self.default or Empty,
      action=self.action,
      help_text=self.help_text,
      compact=self.compact,
    )


class CommandShortcut(BaseModel):
  key: str
  args: list[str] | None = None
  humanized: str | None = None


class MemeArgsType(BaseModel):
  args_model: dict[str, Any]
  args_examples: list[dict[str, Any]]
  parser_options: list[ParserOption]


class MemeParamsType(BaseModel):
  min_images: int
  max_images: int
  min_texts: int
  max_texts: int
  default_texts: list[str]
  args_type: MemeArgsType | None = None


class MemeInfo(BaseModel):
  key: str
  params_type: MemeParamsType
  keywords: list[str]
  shortcuts: list[CommandShortcut]
  tags: set[str]
  date_created: datetime
  date_modified: datetime


CONFIG = SharedConfig("meme_generator", Config, "eager")
lock = anyio.Lock()
matchers = list[type[Matcher]]()
memes = dict[str, MemeInfo]()


@CONFIG.onload()
def _(prev: Config | None, curr: Config) -> None:
  create_background_task(add_matchers())


@nonebot.get_driver().on_startup
async def _() -> None:
  CONFIG()


async def add_matcher(key: str) -> None:
  config = CONFIG()
  http = get_session()
  async with http.get(f"{config.base_url}memes/{key}/info", raise_for_status=True) as response:
    info = MemeInfo.model_validate_json(await response.text())
  memes[key] = info
  options = info.params_type.args_type.parser_options if info.params_type.args_type else []
  matcher = (
    CommandBuilder()
    .node(f"meme_generator.{key}")
    .category("memes")
    .parser(
      Alconna(
        info.keywords[0],
        *(opt.option() for opt in options),
        Args["meme_params", MultiVar(MemeParam, "*")],
      ),
    )
    .aliases(set(info.keywords[1:]))
    .state({"key": key})
    .build()
  )
  matcher.handle()(handle_meme)
  matchers.append(matcher)


async def add_matchers() -> None:
  async with lock:
    for matcher in matchers:
      matcher.destroy()
    matchers.clear()
    config = CONFIG()
    if not config.base_url:
      return
    http = get_session()
    while True:
      try:
        async with http.get(f"{config.base_url}memes/keys", raise_for_status=True) as response:
          keys = TypeAdapter(list[str]).validate_json(await response.text())
          break
      except ClientError:
        logger.exception("初始化 meme_generator 失败")
        await anyio.sleep(10)
    async with anyio.create_task_group() as tg:
      for key in keys:
        tg.start_soon(add_matcher, key)
    random_meme = (
      CommandBuilder()
      .node("meme_generator.random")
      .category("memes")
      .parser(
        Alconna(
          "随机梗图",
          Args["meme_params", MultiVar(MemeParam, "*")],
          meta=CommandMeta("制作符合参数数量的随机梗图"),
        ),
      )
      .build()
    )
    random_meme.handle()(handle_meme_random)
    matchers.append(random_meme)


async def handle_meme_key(
  key: str,
  images: list[MemeImage],
  texts: list[str],
  args: dict[str, Any],
) -> None:
  form = FormData()
  for image in images:
    form.add_field("images", image.image, filename="image")
  for text in texts:
    form.add_field("texts", text)
  form.add_field("args", json.dumps(args))
  async with get_session().post(f"{CONFIG().base_url}memes/{key}/", data=form) as response:
    if response.status != 200:
      error = await response.json()
      await UniMessage(error["detail"]).send()
      return
    data = await response.read()
    mime = response.content_type

  await send_image_or_animation(Image(raw=data, mimetype=mime))


async def handle_meme(
  *,
  event: Event,
  state: T_State,
  meme_params: tuple[MemeParam, ...],
  session: Uninfo,
  interface: QryItrface,
  arp: Arparma[Any],
  reply_info: MaybeReplyInfo,
) -> None:
  key = state["key"]
  info = memes[key]

  try:
    texts, images = await handle_params(
      meme_params,
      reply_info,
      info.params_type.min_images,
      session,
      interface,
      event,
      state,
    )
  except BaseExceptionGroup as excgroup:
    messages = list[str]()
    for exc in flatten_exception_group(excgroup):
      if isinstance(exc, FetchError):
        messages.append(exc.message)
      else:
        messages.append(str(exc))
    await UniMessage("\n".join(messages)).send()
    return

  args = dict[str, Any]()
  for option, result in arp.options.items():
    if result.value is None:
      args.update(result.args)
    else:
      args[option] = result.value

  users = list[dict[str, str]]()
  for image in images:
    if image.name:
      users.append({"name": image.name, "gender": image.gender})
  args["user_infos"] = users

  if info.params_type.min_texts > 0 and len(texts) == 0:
    # 当所需文字数 > 0 且没有输入文字时，使用默认文字
    texts = info.params_type.default_texts

  if not (info.params_type.min_images <= len(images) <= info.params_type.max_images):
    await UniMessage(
      f"输入图片数量不符，图片数量应为 {info.params_type.min_images}"
      + (
        f" ~ {info.params_type.max_images}"
        if info.params_type.max_images > info.params_type.min_images
        else ""
      ),
    ).send()
    return
  if not (info.params_type.min_texts <= len(texts) <= info.params_type.max_texts):
    await UniMessage(
      f"输入文字数量不符，文字数量应为 {info.params_type.min_texts}"
      + (
        f" ~ {info.params_type.max_texts}"
        if info.params_type.max_texts > info.params_type.min_texts
        else ""
      ),
    ).send()
    return

  await handle_meme_key(key, images, texts, args)


async def handle_meme_random(
  event: Event,
  state: T_State,
  meme_params: tuple[MemeParam, ...],
  reply_info: MaybeReplyInfo,
  session: Uninfo,
  interface: QryItrface,
) -> None:
  texts, images = await handle_params(meme_params, reply_info, 0, session, interface, event, state)
  keys = [
    info.key
    for info in memes.values()
    if info.params_type.min_images <= len(images) <= info.params_type.max_images
    and info.params_type.min_texts <= len(texts) <= info.params_type.max_texts
  ]
  if not keys:
    await UniMessage(f"没有适用于 {len(images)} 张图片和 {len(texts)} 段文字的梗图").send()
    return
  await handle_meme_key(random.choice(keys), images, texts, {})
