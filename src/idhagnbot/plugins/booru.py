from contextlib import AbstractAsyncContextManager, AbstractContextManager
from enum import Enum
from functools import cached_property
from os import PathLike
from tempfile import NamedTemporaryFile
from types import TracebackType
from typing import IO, TYPE_CHECKING, Any, AnyStr, Literal, TypeVar, overload
from urllib.parse import quote

import nonebot
from anyio import Path
from anyio.to_thread import run_sync
from arclet.alconna import CommandMeta
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata
from nonebot.typing import T_State
from pydantic import BaseModel, Field, RootModel
from typing_extensions import override

from idhagnbot import SUPPORTED_ADAPTERS
from idhagnbot.asyncio import gather_seq
from idhagnbot.command import CommandBuilder
from idhagnbot.config import SharedConfig
from idhagnbot.http import get_session
from idhagnbot.i18n import bound_lang
from idhagnbot.permission import DEFAULT

if TYPE_CHECKING:
  from tempfile import _TemporaryFileWrapper  # pyright: ignore[reportPrivateUsage]

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_localstore")
nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import Alconna, Args, Image, MultiVar, Option, Query, Text, UniMessage
from nonebot_plugin_localstore import get_cache_dir
from nonebot_plugin_uninfo import Uninfo

__plugin_meta__ = PluginMetadata(
  name="IdhagnBot Booru",
  description="搜索 Booru 类网站。",
  usage="在配置文件 `configs/idhagnbot/booru.yaml` 中配置想要的网站，然后使用对应的命令搜索图片。"
  "配置文件可用预设，参见对应网站底部信息或者 https://booru.neocities.org/ 得知需要使用何种预设。",
  type="application",
  homepage="https://github.com/su226/IdhagnBot-Next",
  supported_adapters=SUPPORTED_ADAPTERS,
)


class JsonPointer(RootModel[str]):
  @cached_property
  def segments(self) -> tuple[str, ...]:
    trimmed = self.root.removeprefix("/")
    if not trimmed:
      return ()
    return tuple(x.replace("~1", "/").replace("~0", "~") for x in trimmed.split("/"))

  def select(self, target: Any) -> Any:
    for segment in self.segments:
      target = target[int(segment) if isinstance(target, list) else segment]
    return target


class CustomSample(BaseModel):
  url: str
  param_ptr: JsonPointer | None = None


class VotePath(BaseModel):
  up: JsonPointer
  down: JsonPointer | None = None


class DimensionsPath(BaseModel):
  width: JsonPointer
  height: JsonPointer


class SizePath(BaseModel):
  size: JsonPointer
  multiplier: int | None = 1


class Site(BaseModel):
  # Required - Or you will get an error.
  origin: str
  post_url: str
  api_url: str
  array_ptr: JsonPointer
  id_ptr: JsonPointer
  sample_ptr: list[JsonPointer | CustomSample]
  # Optional - Missing fields won't be displayed.
  max_page_size: int = 0
  vote_ptr: VotePath | None = None
  favorite_ptr: JsonPointer | None = None
  comment_ptr: JsonPointer | None = None
  rating_ptr: JsonPointer | None = None
  dimensions_ptr: DimensionsPath | None = None
  size_ptr: SizePath | None = None
  extension_ptr: JsonPointer | None = None


PRESETS = {
  "gelbooru": Site(
    origin="https://gelbooru.com",
    post_url="/index.php?page=post&s=view&id={id}",
    api_url="/index.php?page=dapi&s=post&q=index&tags={tags}&limit={limit}&pid={page}&json=1",
    array_ptr=JsonPointer("/"),
    id_ptr=JsonPointer("/id"),
    sample_ptr=[JsonPointer("/sample_url")],
    max_page_size=1000,
    vote_ptr=VotePath(up=JsonPointer("/score")),
    favorite_ptr=None,
    comment_ptr=JsonPointer("/comment_count"),
    rating_ptr=JsonPointer("/rating"),
    dimensions_ptr=DimensionsPath(width=JsonPointer("/width"), height=JsonPointer("/height")),
    size_ptr=None,
    extension_ptr=JsonPointer("/file_url"),
  ),
  "danbooru": Site(
    origin="https://danbooru.donmai.us",
    post_url="/posts/{id}",
    api_url="/posts.json?tags={tags}&limit={limit}&page={page}",
    array_ptr=JsonPointer("/"),
    id_ptr=JsonPointer("/id"),
    sample_ptr=[JsonPointer("/large_file_url"), JsonPointer("/preview_file_url")],
    max_page_size=200,
    vote_ptr=VotePath(up=JsonPointer("/up_score"), down=JsonPointer("/down_score")),
    favorite_ptr=JsonPointer("/fav_count"),
    comment_ptr=None,
    rating_ptr=JsonPointer("/rating"),
    dimensions_ptr=DimensionsPath(
      width=JsonPointer("/image_width"),
      height=JsonPointer("/image_height"),
    ),
    size_ptr=SizePath(size=JsonPointer("/file_size")),
    extension_ptr=JsonPointer("/file_ext"),
  ),
  "moebooru": Site(
    origin="https://konachan.com",
    post_url="/post/show/{id}",
    api_url="/post.json?tags={tags}&limit={limit}&page={page}",
    array_ptr=JsonPointer("/"),
    id_ptr=JsonPointer("/id"),
    sample_ptr=[JsonPointer("/sample_url")],
    max_page_size=1000,
    vote_ptr=VotePath(up=JsonPointer("/score")),
    favorite_ptr=None,
    comment_ptr=None,
    rating_ptr=JsonPointer("/rating"),
    dimensions_ptr=DimensionsPath(width=JsonPointer("/width"), height=JsonPointer("/height")),
    size_ptr=SizePath(size=JsonPointer("/file_size")),
    extension_ptr=JsonPointer("/file_url"),
  ),
  "e621": Site(
    origin="https://e621.net",
    post_url="/posts/{id}",
    api_url="/posts.json?tags={tags}&limit={limit}&page={page}",
    array_ptr=JsonPointer("/posts"),
    id_ptr=JsonPointer("/id"),
    sample_ptr=[JsonPointer("/sample/url"), JsonPointer("/preview/url")],
    max_page_size=320,
    vote_ptr=VotePath(up=JsonPointer("/score/up"), down=JsonPointer("/score/down")),
    favorite_ptr=JsonPointer("/fav_count"),
    comment_ptr=JsonPointer("/comment_count"),
    rating_ptr=JsonPointer("/rating"),
    dimensions_ptr=DimensionsPath(
      width=JsonPointer("/file/width"),
      height=JsonPointer("/file/height"),
    ),
    size_ptr=SizePath(size=JsonPointer("/file/size")),
    extension_ptr=JsonPointer("/file/ext"),
  ),
  "philomena": Site(
    origin="https://derpibooru.org",
    post_url="/images/{id}",
    api_url="/api/v1/json/search/images?q={tags}&per_page={limit}&page={page}",
    array_ptr=JsonPointer("/images"),
    id_ptr=JsonPointer("/id"),
    sample_ptr=[JsonPointer("/representations/medium")],
    max_page_size=50,
    vote_ptr=VotePath(up=JsonPointer("/upvotes"), down=JsonPointer("/downvotes")),
    favorite_ptr=JsonPointer("/faves"),
    comment_ptr=JsonPointer("/comment_count"),
    rating_ptr=None,
    dimensions_ptr=DimensionsPath(width=JsonPointer("/width"), height=JsonPointer("/height")),
    size_ptr=SizePath(size=JsonPointer("/size")),
    extension_ptr=JsonPointer("/format"),
  ),
  "hybooru": Site(
    origin="https://booru.funmaker.moe",
    post_url="/posts/{id}",
    api_url="/api/post?query={tags}&pageSize={limit}&page={page}",
    array_ptr=JsonPointer("/posts"),
    id_ptr=JsonPointer("/id"),
    sample_ptr=[CustomSample(url="/files/t{param}.thumbnail", param_ptr=JsonPointer("/sha256"))],
    max_page_size=72,
    vote_ptr=None,
    favorite_ptr=None,
    comment_ptr=None,
    rating_ptr=None,
    dimensions_ptr=None,
    size_ptr=SizePath(size=JsonPointer("/size")),
    extension_ptr=JsonPointer("/extension"),
  ),
  "szurubooru": Site(
    origin="https://szuru.libre.moe",
    post_url="/post/{id}",
    api_url="/api/posts/?query={tags}&offset={offset}&limit={limit}",
    array_ptr=JsonPointer("/results"),
    id_ptr=JsonPointer("/id"),
    sample_ptr=[JsonPointer("/thumbnailUrl")],
    max_page_size=100,
    vote_ptr=VotePath(up=JsonPointer("/score")),
    favorite_ptr=JsonPointer("/favoriteCount"),
    comment_ptr=JsonPointer("/commentCount"),
    rating_ptr=JsonPointer("/safety"),
    dimensions_ptr=None,
    size_ptr=None,
    extension_ptr=None,
  ),
}
EMPTY_PRESET = {
  "origin": None,
  "post_url": None,
  "api_url": None,
  "array_ptr": None,
  "id_ptr": None,
  "sample_ptr": None,
  "max_page_size": 0,
  "vote_ptr": None,
  "favorite_ptr": None,
  "comment_ptr": None,
  "rating_ptr": None,
  "dimensions_ptr": None,
  "size_ptr": None,
  "extension_ptr": None,
}


class Command(BaseModel):
  id: str
  name: str
  aliases: dict[str, str | None] = Field(default_factory=dict)
  brief: str = ""
  default_grant_to: set[str] = Field(default_factory=DEFAULT.copy)
  headers: dict[str, str] = Field(default_factory=dict)
  proxy: str | None = None
  preset: str | None = None
  origin: str | None = None
  post_url: str | None = None
  api_url: str | None = None
  array_ptr: str | None = None
  id_ptr: str | None = None
  sample_ptr: list[str | CustomSample] | None = None
  max_page_size: int | None = None
  vote_ptr: VotePath | None = None
  favorite_ptr: str | None = None
  comment_ptr: str | None = None
  rating_ptr: str | None = None
  dimensions_ptr: DimensionsPath | None = None
  size_ptr: SizePath | None = None
  extension_ptr: str | None = None

  def to_site(self, preset: Site | None = None) -> Site:
    base = EMPTY_PRESET if preset is None else preset.model_dump()
    overlay = self.model_dump()
    return Site.model_validate(
      {
        key: value if (overlay_value := overlay[key]) is None else overlay_value
        for key, value in base.items()
      },
    )


class PageSize(BaseModel):
  default: int
  max: int


class Config(BaseModel):
  page_size: PageSize = PageSize(default=10, max=10)
  platform_page_size: dict[str, PageSize] = Field(default_factory=dict)
  presets: dict[str, Site] = Field(default_factory=dict)
  commands: list[Command] = Field(default_factory=list)

  def get_preset(self, name: str) -> Site:
    return self.presets[name] if name in self.presets else PRESETS[name]


CONFIG = SharedConfig("booru", Config)
L = bound_lang("idhagnbot_booru")
CACHE_DIR = Path(get_cache_dir("idhagnbot") / "booru")
driver = nonebot.get_driver()
matchers = list[type[Matcher]]()


@CONFIG.onload()
def _(prev: Config | None, curr: Config) -> None:
  for matcher in matchers:
    matcher.destroy()
  matchers.clear()
  for command in curr.commands:
    preset = curr.get_preset(command.preset) if command.preset else None
    matcher = (
      CommandBuilder()
      .node(f"booru.{command.id}")
      .parser(
        Alconna(
          command.name,
          Args["tags", MultiVar(str, "*")],
          Option("--page|-p", Args["page", int]),
          Option("--limit|-l", Args["limit", int]),
          meta=CommandMeta(command.brief),
        ),
      )
      .aliases(command.aliases)
      .state({"site": command.to_site(preset), "proxy": command.proxy, "headers": command.headers})
      .build()
    )
    matcher.handle()(handle_booru)
    matchers.append(matcher)


@driver.on_startup
async def _() -> None:
  CONFIG()


def is_sample_valid(url: Any) -> bool:
  return isinstance(url, str) and not url.endswith((".mp4", ".webm"))


def format_size(size: int) -> str:
  fsize = size / 1024
  if fsize < 1024:
    return f"{fsize:.1f}k"
  fsize /= 1024
  if fsize < 1024:
    return f"{fsize:.1f}M"
  fsize /= 1024
  return f"{fsize:.1f}G"


def get_extension(url_or_ext: str) -> str:
  try:
    return url_or_ext[url_or_ext.rindex(".") + 1 :]
  except ValueError:
    return url_or_ext


def url_to_absolute(origin: str, path: str) -> str:
  if not path.startswith(("http:", "https:")):
    if not path.startswith("/"):
      return origin + "/" + path
    return origin + path
  return path


OpenTextModeUpdating = Literal[
  "r+",
  "+r",
  "rt+",
  "r+t",
  "+rt",
  "tr+",
  "t+r",
  "+tr",
  "w+",
  "+w",
  "wt+",
  "w+t",
  "+wt",
  "tw+",
  "t+w",
  "+tw",
  "a+",
  "+a",
  "at+",
  "a+t",
  "+at",
  "ta+",
  "t+a",
  "+ta",
  "x+",
  "+x",
  "xt+",
  "x+t",
  "+xt",
  "tx+",
  "t+x",
  "+tx",
]
OpenTextModeWriting = Literal["w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"]
OpenTextModeReading = Literal[
  "r",
  "rt",
  "tr",
  "U",
  "rU",
  "Ur",
  "rtU",
  "rUt",
  "Urt",
  "trU",
  "tUr",
  "Utr",
]
OpenTextMode = OpenTextModeUpdating | OpenTextModeWriting | OpenTextModeReading
OpenBinaryModeUpdating = Literal[
  "rb+",
  "r+b",
  "+rb",
  "br+",
  "b+r",
  "+br",
  "wb+",
  "w+b",
  "+wb",
  "bw+",
  "b+w",
  "+bw",
  "ab+",
  "a+b",
  "+ab",
  "ba+",
  "b+a",
  "+ba",
  "xb+",
  "x+b",
  "+xb",
  "bx+",
  "b+x",
  "+bx",
]
OpenBinaryModeWriting = Literal["wb", "bw", "ab", "ba", "xb", "bx"]
OpenBinaryModeReading = Literal["rb", "br", "rbU", "rUb", "Urb", "brU", "bUr", "Ubr"]
OpenBinaryMode = OpenBinaryModeUpdating | OpenBinaryModeReading | OpenBinaryModeWriting


class TempFiles(AbstractContextManager[list["_TemporaryFileWrapper[AnyStr]"], None]):
  @overload
  def __init__(
    self: "TempFiles[str]",
    mode: OpenTextMode,
    count: int,
    dir: PathLike[Any] | None = None,
  ) -> None: ...
  @overload
  def __init__(
    self: "TempFiles[bytes]",
    mode: OpenBinaryMode,
    count: int,
    dir: PathLike[Any] | None = None,
  ) -> None: ...
  def __init__(
    self,
    mode: OpenTextMode | OpenBinaryMode,
    count: int,
    dir: PathLike[Any] | None = None,  # noqa: A002
  ) -> None:
    self.__files = [NamedTemporaryFile(mode, dir=dir) for _ in range(count)]  # noqa: SIM115

  @override
  def __enter__(self) -> list["_TemporaryFileWrapper[AnyStr]"]:
    super().__enter__()
    for file in self.__files:
      file.__enter__()
    return self.__files

  @override
  def __exit__(
    self,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    traceback: TracebackType | None,
  ) -> None:
    for file in self.__files:
      file.__exit__(exc_type, exc_value, traceback)


TEnter_co = TypeVar("TEnter_co", covariant=True)
TExit_co = TypeVar("TExit_co", covariant=True, bound=bool | None)


class AsyncContextWrapper(AbstractAsyncContextManager[TEnter_co, TExit_co]):
  def __init__(self, sync: AbstractContextManager[TEnter_co, TExit_co]) -> None:
    self.__sync = sync

  @override
  async def __aenter__(self) -> TEnter_co:
    return await run_sync(self.__sync.__enter__)

  @override
  async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    traceback: TracebackType | None,
  ) -> TExit_co:
    return await run_sync(self.__sync.__exit__, exc_type, exc_value, traceback)


async def handle_booru(
  session: Uninfo,
  state: T_State,
  tags: tuple[str, ...],
  page: Query[int] = Query("page"),
  limit: Query[int] = Query("limit"),
) -> None:
  config = CONFIG()
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  page_size_config = config.platform_page_size.get(scope, config.page_size)
  site: Site = state["site"]
  proxy: str | None = state["proxy"]
  headers: dict[str, str] = state["headers"]
  if limit.available:
    page_size_max = page_size_config.max
    if site.max_page_size > 0:
      page_size_max = min(page_size_max, site.max_page_size)
    page_size = limit.result
    if not (1 <= page_size <= page_size_max):
      await UniMessage.text(L("invalid_page_size").format(max=page_size_max)).finish()
  else:
    page_size = page_size_config.default
    if site.max_page_size > 0:
      page_size = min(page_size, site.max_page_size)
  if page.available:
    page_current = page.result
    if page_current < 1:
      await UniMessage.text(L("invalid_page")).finish()
  else:
    page_current = 1
  offset = (page_current - 1) * page_size

  http = get_session()
  api_url = url_to_absolute(
    site.origin,
    site.api_url.format(
      tags=quote(" ".join(tags)),
      limit=page_size,
      page=page_current,
      offset=offset,
    ),
  )

  async with http.get(api_url, headers=headers, proxy=proxy, raise_for_status=True) as response:
    data = await response.json()

  posts = site.array_ptr.select(data)
  if not posts:
    await UniMessage(L("posts_empty")).finish()

  await CACHE_DIR.mkdir(parents=True, exist_ok=True)
  async with AsyncContextWrapper(TempFiles("wb", len(posts), dir=CACHE_DIR)) as files:

    async def download_post(post: Any, file: IO[bytes]) -> None:
      post_id = site.id_ptr.select(post)
      url = None
      for ptr in site.sample_ptr:
        if isinstance(ptr, CustomSample):
          param = "" if ptr.param_ptr is None else ptr.param_ptr.select(post)
          url = ptr.url.format(id=post_id, param=param)
        else:
          url = ptr.select(post)
        if not is_sample_valid(url):
          continue
      if url is None:
        raise ValueError("未找到合适的预览 URL")
      url = url_to_absolute(site.origin, url)
      async with http.get(url, headers=headers, proxy=proxy, raise_for_status=True) as response:
        async for chunk in response.content.iter_chunked(65536):
          await run_sync(file.write, chunk)
      await run_sync(file.flush)

    await gather_seq(download_post(post, file) for post, file in zip(posts, files, strict=True))
    message = UniMessage()
    for post, file in zip(posts, files, strict=True):
      post_id = site.id_ptr.select(post)
      url = url_to_absolute(site.origin, site.post_url.format(id=post_id))
      infos = list[str]()
      if site.vote_ptr is not None:
        vote = site.vote_ptr.up.select(post) or 0
        if site.vote_ptr.down is not None:
          vote -= abs(site.vote_ptr.down.select(post) or 0)
        infos.append(f"👎 {-vote}" if vote < 0 else f"👍 {vote}")
      if site.favorite_ptr is not None:
        favorite = site.favorite_ptr.select(post) or 0
        infos.append(f"⭐ {favorite}")
      if site.comment_ptr is not None:
        comment = site.comment_ptr.select(post) or 0
        infos.append(f"💬 {comment}")
      if site.rating_ptr is not None:
        rating = site.rating_ptr.select(post)
        infos.append(rating)
      if site.dimensions_ptr is not None:
        width = site.dimensions_ptr.width.select(post)
        height = site.dimensions_ptr.height.select(post)
        infos.append(f"{width}x{height}")
      if site.size_ptr is not None:
        size = site.size_ptr.size.select(post)
        infos.append(format_size(size * site.size_ptr.multiplier))
      if site.extension_ptr is not None:
        extension = site.extension_ptr.select(post)
        infos.append(get_extension(extension).upper())
      if message:
        message.append(Text.br())
      message.append(Image(path=file.name))
      message.append(Text.br())
      message.append(Text(url))
      if infos:
        message.append(Text.br())
        message.append(Text(" | ".join(infos)))

    await message.send()
