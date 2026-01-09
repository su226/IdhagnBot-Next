import math
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from urllib.parse import quote as encodeuri

from pydantic import TypeAdapter
from typing_extensions import Self, TypedDict, override

from idhagnbot.http import get_session
from idhagnbot.plugins.music.sources.base import AudioUrl, Music, SearchResult

SEARCH_API = (
  "https://music.163.com/api/search/get/web?type=1&offset={offset}&limit={limit}&s={keyword}"
)
INFO_API = "http://music.163.com/api/song/detail/?ids=[{id}]"
PAGE_SIZE = 100


class ApiSearchAlbum(TypedDict):
  name: str


class ApiSearchArtist(TypedDict):
  name: str


class ApiSearchSong(TypedDict):
  album: ApiSearchAlbum
  fee: int
  id: int
  artists: list[ApiSearchArtist]
  name: str


class ApiSearchInner(TypedDict):
  songs: list[ApiSearchSong]
  songCount: int


class ApiSearch(TypedDict):
  result: ApiSearchInner


class ApiInfoArtist(TypedDict):
  name: str


class ApiInfoAlbum(TypedDict):
  name: str
  picUrl: str


class ApiInfoSong(TypedDict):
  name: str
  fee: int
  artists: list[ApiInfoArtist]
  album: ApiInfoAlbum


class ApiInfo(TypedDict):
  songs: list[ApiInfoSong]


@dataclass
class NeteaseMusic(Music):
  id: int
  _info: ApiInfoSong | None = field(default=None, init=False)

  @property
  @override
  def detail_url(self) -> str:
    return f"https://music.163.com/#/song?id={self.id}"

  @override
  async def get_cover_url(self) -> str:
    if not self._info:
      async with get_session().get(INFO_API.format(id=self.id)) as response:
        data = TypeAdapter(ApiInfo).validate_json(await response.text())
      self._info = data["songs"][0]
    return self._info["album"]["picUrl"]

  @override
  async def get_audio_url(self) -> AudioUrl:
    return AudioUrl(f"http://music.163.com/song/media/outer/url?id={self.id}", "mp3")

  @classmethod
  @override
  async def from_id(cls, music_id: str) -> Self:
    id_int = int(music_id)
    async with get_session().get(INFO_API.format(id=id_int)) as response:
      data = TypeAdapter(ApiInfo).validate_json(await response.text())
    if not data["songs"]:
      raise ValueError("ID 不存在")
    info = data["songs"][0]
    music = cls(
      info["name"],
      [x["name"] for x in info["artists"]],
      info["album"]["name"],
      info["fee"] == 1,
      id_int,
    )
    music._info = info
    return music

  @classmethod
  @override
  async def search(cls, keyword: str) -> SearchResult[Self]:
    http = get_session()
    keyword = encodeuri(keyword)
    adapter = TypeAdapter(ApiSearch)
    async with http.get(
      SEARCH_API.format(keyword=keyword, offset=0, limit=PAGE_SIZE),
    ) as response:
      data = adapter.validate_json(await response.text())
    count = data["result"]["songCount"]
    pages = math.ceil(count / PAGE_SIZE)

    async def _musics() -> AsyncGenerator[Self, None]:
      nonlocal data
      page = 0
      while True:
        for song in data["result"]["songs"]:
          yield cls(
            song["name"],
            [x["name"] for x in song["artists"]],
            song["album"]["name"],
            song["fee"] == 1,
            song["id"],
          )
        page += 1
        if page >= pages:
          break
        async with http.get(
          SEARCH_API.format(keyword=keyword, offset=page * PAGE_SIZE, limit=PAGE_SIZE),
        ) as response:
          data = adapter.validate_json(await response.text())

    return SearchResult(count, _musics())
