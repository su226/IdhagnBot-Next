from dataclasses import dataclass
from typing import Generic, Self, TypeVar

from typing_extensions import AsyncGenerator

T_co = TypeVar("T_co", bound="Music", covariant=True)


@dataclass
class SearchResult(Generic[T_co]):
  count: int
  musics: AsyncGenerator[T_co, None]


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
