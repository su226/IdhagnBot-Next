from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Self


@dataclass
class SearchResult[T: Music]:
    count: int
    musics: AsyncGenerator[T]


@dataclass
class AudioUrl:
    url: str
    extension: str


@dataclass
class Music:
    name: str
    artists: list[str]
    album: str
    unavailable: bool

    @property
    def detail_url(self) -> str:
        raise NotImplementedError

    async def get_cover_url(self) -> str:
        raise NotImplementedError

    async def get_audio_url(self) -> AudioUrl:
        raise NotImplementedError

    @classmethod
    async def from_id(cls, music_id: str) -> Self:
        raise ValueError("该来源不支持从 ID 获取")

    @classmethod
    async def search(cls, keyword: str) -> SearchResult[Self]:
        raise NotImplementedError
