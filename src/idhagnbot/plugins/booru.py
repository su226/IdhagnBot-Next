from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack
from dataclasses import dataclass
from functools import cached_property
from typing import Any
from urllib.parse import quote

from anyio import AsyncFile, NamedTemporaryFile, Path
from arclet.alconna import Alconna, Args, CommandMeta, MultiVar, Option
from arclet.entari import (
    Image,
    MessageChain,
    Session,
    Text,
    command,
    local_data,
    metadata,
    plugin_config,
)
from arclet.entari.command import Query
from entari_plugin_permission import require_permission
from pydantic import BaseModel, Field, RootModel
from satori.element import Br

from idhagnbot.asyncio import gather_seq
from idhagnbot.http import get_session
from idhagnbot.i18n import bound_lang


class JsonPointer(RootModel[str]):
    @cached_property
    def segments(self) -> tuple[str, ...]:
        trimmed = self.root.removeprefix("/")
        if not trimmed:
            return ()
        return tuple(
            x.replace("~1", "/").replace("~0", "~") for x in trimmed.split("/")
        )

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
        dimensions_ptr=DimensionsPath(
            width=JsonPointer("/width"),
            height=JsonPointer("/height"),
        ),
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
        dimensions_ptr=DimensionsPath(
            width=JsonPointer("/width"),
            height=JsonPointer("/height"),
        ),
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
        dimensions_ptr=DimensionsPath(
            width=JsonPointer("/width"),
            height=JsonPointer("/height"),
        ),
        size_ptr=SizePath(size=JsonPointer("/size")),
        extension_ptr=JsonPointer("/format"),
    ),
    "hybooru": Site(
        origin="https://booru.funmaker.moe",
        post_url="/posts/{id}",
        api_url="/api/post?query={tags}&pageSize={limit}&page={page}",
        array_ptr=JsonPointer("/posts"),
        id_ptr=JsonPointer("/id"),
        sample_ptr=[
            CustomSample(
                url="/files/t{param}.thumbnail",
                param_ptr=JsonPointer("/sha256"),
            ),
        ],
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
    default_available: bool = True
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


metadata("", config=Config)
CONFIG = plugin_config(Config)
L = bound_lang("idhagnbot_booru")
CACHE_DIR = Path(local_data.get_cache_dir("idhagnbot") / "booru")


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


@dataclass
class BooruHandler:
    site: Site
    proxy: str | None
    headers: dict[str, str]

    async def handle(
        self,
        session: Session,
        tags: tuple[str, ...],
        page: Query[int] = Query("page"),
        limit: Query[int] = Query("limit"),
    ) -> AsyncGenerator[str | MessageChain]:
        page_size_config = CONFIG.platform_page_size.get(
            session.account.platform,
            CONFIG.page_size,
        )
        if limit.available:
            page_size_max = page_size_config.max
            if self.site.max_page_size > 0:
                page_size_max = min(page_size_max, self.site.max_page_size)
            page_size = limit.result
            if not (1 <= page_size <= page_size_max):
                yield L("invalid_page_size").format(max=page_size_max)
                return
        else:
            page_size = page_size_config.default
            if self.site.max_page_size > 0:
                page_size = min(page_size, self.site.max_page_size)
        if page.available:
            page_current = page.result
            if page_current < 1:
                yield L("invalid_page")
                return
        else:
            page_current = 1
        offset = (page_current - 1) * page_size

        http = get_session()
        api_url = url_to_absolute(
            self.site.origin,
            self.site.api_url.format(
                tags=quote(" ".join(tags)),
                limit=page_size,
                page=page_current,
                offset=offset,
            ),
        )

        async with http.get(
            api_url,
            headers=self.headers,
            proxy=self.proxy,
            raise_for_status=True,
        ) as response:
            data = await response.json()

        posts = self.site.array_ptr.select(data)
        if not posts:
            yield L("posts_empty")
            return

        await CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_dir = str(CACHE_DIR)
        async with AsyncExitStack() as stack:
            files = await gather_seq(
                stack.enter_async_context(NamedTemporaryFile("wb", dir=cache_dir))
                for _ in range(len(posts))
            )

            async def download_post(post: Any, file: AsyncFile[bytes]) -> None:
                post_id = self.site.id_ptr.select(post)
                url = None
                for ptr in self.site.sample_ptr:
                    if isinstance(ptr, CustomSample):
                        param = (
                            "" if ptr.param_ptr is None else ptr.param_ptr.select(post)
                        )
                        url = ptr.url.format(id=post_id, param=param)
                    else:
                        url = ptr.select(post)
                    if not is_sample_valid(url):
                        continue
                if url is None:
                    raise ValueError("未找到合适的预览 URL")
                url = url_to_absolute(self.site.origin, url)
                async with http.get(
                    url,
                    headers=self.headers,
                    proxy=self.proxy,
                    raise_for_status=True,
                ) as response:
                    async for chunk in response.content.iter_chunked(65536):
                        await file.write(chunk)
                await file.flush()

            await gather_seq(
                download_post(post, file)
                for post, file in zip(posts, files, strict=True)
            )
            message = MessageChain()
            for post, file in zip(posts, files, strict=True):
                post_id = self.site.id_ptr.select(post)
                url = url_to_absolute(
                    self.site.origin,
                    self.site.post_url.format(id=post_id),
                )
                infos = list[str]()
                if self.site.vote_ptr is not None:
                    vote = self.site.vote_ptr.up.select(post) or 0
                    if self.site.vote_ptr.down is not None:
                        vote -= abs(self.site.vote_ptr.down.select(post) or 0)
                    infos.append(f"👎 {-vote}" if vote < 0 else f"👍 {vote}")
                if self.site.favorite_ptr is not None:
                    favorite = self.site.favorite_ptr.select(post) or 0
                    infos.append(f"⭐ {favorite}")
                if self.site.comment_ptr is not None:
                    comment = self.site.comment_ptr.select(post) or 0
                    infos.append(f"💬 {comment}")
                if self.site.rating_ptr is not None:
                    rating = self.site.rating_ptr.select(post)
                    infos.append(rating)
                if self.site.dimensions_ptr is not None:
                    width = self.site.dimensions_ptr.width.select(post)
                    height = self.site.dimensions_ptr.height.select(post)
                    infos.append(f"{width}x{height}")
                if self.site.size_ptr is not None:
                    size = self.site.size_ptr.size.select(post)
                    infos.append(format_size(size * self.site.size_ptr.multiplier))
                if self.site.extension_ptr is not None:
                    extension = self.site.extension_ptr.select(post)
                    infos.append(get_extension(extension).upper())
                if message:
                    message.append(Br())
                message.append(Image.of(path=file.wrapped.name))
                message.append(Br())
                message.append(Text(url))
                if infos:
                    message.append(Br())
                    message.append(Text(" | ".join(infos)))

            yield message


for conf in CONFIG.commands:
    preset = CONFIG.get_preset(conf.preset) if conf.preset else None
    cmd = Alconna(
        conf.name,
        Args["tags", MultiVar(str, "*")],
        Option("--page|-p", Args["page", int]),
        Option("--limit|-l", Args["limit", int]),
        meta=CommandMeta(conf.brief, extra={"idhagnbot_i18n_names": conf.aliases}),
    )
    for alias in conf.aliases:
        if alias != conf.name:
            cmd.shortcut(alias, command=conf.name)
    subscriber = command.on(cmd)(
        BooruHandler(conf.to_site(preset), conf.proxy, conf.headers).handle,
    )
    subscriber.propagate(
        require_permission(
            f"idhagnbot.booru.{conf.id}",
            conf.default_available,
            prompt=True,
        ),
    )
