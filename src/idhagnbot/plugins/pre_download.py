from asyncio import TaskGroup, gather
from collections.abc import Sequence
from datetime import datetime, timedelta
from mimetypes import guess_extension
from pathlib import Path

from aiohttp import ClientTimeout
from anyio import Path as APath
from anyio import mkstemp, open_file
from arclet.entari import Cleanup, MessageChain, SendRequest, local_data, plugin_config
from arclet.entari.scheduler import every
from arclet.letoderea import on
from pydantic import BaseModel, HttpUrl
from satori import Audio, Element, Image, Video
from satori import File as FileEl
from satori.element import Resource

from idhagnbot.http import get_session


class Config(BaseModel):
    enabled: bool = False
    proxy: HttpUrl | None = None


CONFIG = plugin_config(Config, bind=True)
DIR = local_data.get_cache_dir("idhagnbot") / "pre_download"
DIR.mkdir(parents=True, exist_ok=True)
HasPoster = Video | Audio | FileEl


def _extract_poster(poster: str | None) -> str | None:
    if poster and poster.startswith(("http://", "https://")):
        return poster
    return None


async def _download(src: str, timeout: float | None) -> Path:  # noqa: ASYNC109
    async with get_session().get(src, timeout=ClientTimeout(timeout)) as response:
        extension = guess_extension(response.content_type)
        fd, path = await mkstemp(extension, dir=str(DIR))
        file = await open_file(fd, "wb")
        async for chunk in response.content.iter_chunked(65536):
            await file.write(chunk)
    return Path(path)


async def _download_src_and_poster(element: HasPoster, poster: str) -> None:
    path, poster_path = await gather(
        _download(element.src, element.timeout),
        _download(poster, element.timeout),
    )
    element._attrs.pop("cache", None)
    element._attrs.pop("timeout", None)
    element._attrs["src"] = path.as_uri()
    element._attrs["poster"] = poster_path.as_uri()


async def _download_src(element: Resource) -> None:
    path = await _download(element.src, element.timeout)
    element._attrs.pop("cache", None)
    element._attrs.pop("timeout", None)
    element._attrs["src"] = path.as_uri()


async def _download_poster(element: HasPoster, poster: str) -> None:
    poster_path = await _download(poster, element.timeout)
    element._attrs.pop("cache", None)
    element._attrs.pop("timeout", None)
    element._attrs["poster"] = poster_path.as_uri()


def _traverse(message: Sequence[Element], tg: TaskGroup) -> None:
    for element in message:
        if isinstance(element, Image):
            if element.src.startswith(("http://", "https://")):
                tg.create_task(_download_src(element))
        elif isinstance(element, HasPoster):
            need_download_src = element.src.startswith(("http://", "https://"))
            poster = _extract_poster(element.poster)
            if need_download_src and poster:
                tg.create_task(_download_src_and_poster(element, poster))
            elif need_download_src:
                tg.create_task(_download_src(element))
            elif poster:
                tg.create_task(_download_poster(element, poster))
        _traverse(element.children, tg)


async def download_and_modify_src(message: MessageChain) -> None:
    async with TaskGroup() as tg:
        _traverse(message, tg)


@on(SendRequest)
async def pre_download(message: MessageChain) -> MessageChain:
    if CONFIG.enabled:
        await download_and_modify_src(message)
    return message


@on(Cleanup)
async def clean_shutdown() -> None:
    async with TaskGroup() as tg:
        async for file in APath(DIR).iterdir():
            tg.create_task(file.unlink(missing_ok=True))


async def _clean_one(path: APath, threshold: float) -> None:
    st = await path.stat(follow_symlinks=False)
    if st.st_mtime < threshold:
        await path.unlink(missing_ok=True)


@every(5, "minute")
async def clean_scheduled() -> None:
    threshold = (datetime.now() - timedelta(minutes=5)).timestamp()
    async with TaskGroup() as tg:
        async for file in APath(DIR).iterdir():
            tg.create_task(_clean_one(file, threshold))
