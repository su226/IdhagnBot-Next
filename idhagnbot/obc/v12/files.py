import hashlib
import json
import os
from datetime import datetime
from typing import BinaryIO, Dict, Optional, Union, cast
from uuid import UUID, uuid4

from aiohttp import ClientError, ClientSession
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, MetaData, SQLModel, select

from idhagnbot.concurrent import to_thread
from idhagnbot.obc.model import Model
from idhagnbot.obc.v12.action import (
  GetFileDataResult, GetFileParam, GetFilePathResult, GetFileResult, GetFileURLResult,
  UploadFileParam, UploadFileResult
)
from idhagnbot.obc.v12.app import ActionResult, ActionResultTuple
from idhagnbot.obc.v12.event import BotSelf


class URLFileMetadata(BaseModel):
  url: str
  headers: Dict[str, str]


class File(SQLModel, table=True):
  metadata = MetaData()
  id: UUID = Field(primary_key=True)
  type: str
  name: str
  path: str
  time: datetime
  sha256: str
  meta: str


class DeleteFileParam(Model):
  file_id: str


DeleteFileResult = Model


def calc_file_sha256(path: Union[str, BinaryIO], *, chunk_size: int = 16384) -> str:
  if isinstance(path, str):
    f = open(path, "rb")
    close = True
  else:
    f = path
    close = False
  try:
    hash = hashlib.sha256()
    while True:
      data = f.read(chunk_size)
      if not data:
        return hash.hexdigest()
      hash.update(data)
  finally:
    if close:
      f.close()


class DatabaseFileManager:
  def __init__(self, dir: str, http: ClientSession) -> None:
    self.__engine = create_async_engine(f"sqlite+aiosqlite:///{dir}/files.db")
    self.__dir = os.path.abspath(dir)
    self.__http = http

  @property
  def dir(self) -> str:
    return self.__dir

  async def setup(self) -> None:
    os.makedirs(self.__dir, exist_ok=True)
    async with self.__engine.begin() as connection:
      await connection.run_sync(File.metadata.create_all)

  async def upload_file(
    self,
    params: UploadFileParam,
    _bot_self: Optional[BotSelf] = None,
  ) -> ActionResultTuple[UploadFileResult]:
    id = uuid4()
    time = datetime.now()
    sha256 = ""
    metadata = ""
    if params.type == "url":
      def write_file() -> None:
        nonlocal sha256
        sha256 = hashlib.sha256(data).hexdigest()
        if params.sha256 and sha256 != params.sha256.lower():
          raise ActionResult(35003, f"SHA-256 mismatch: {params.sha256}", None)
        with open(file_path, "wb") as f:
          f.write(data)
      metadata = URLFileMetadata(
        url=params.url,
        headers=params.headers,
      ).json()
      try:
        async with self.__http.get(params.url, headers=params.headers) as response:
          data = await response.read()
      except ClientError as e:
        return 33000, str(e), None
      try:
        file_path = os.path.join(self.__dir, str(id))
        await to_thread(write_file)
      except OSError as e:
        return 32000, str(e), None
    elif params.type == "path":
      try:
        file_path = os.path.abspath(params.path)
        sha256 = await to_thread(calc_file_sha256, file_path)
      except OSError as e:
        return 32000, str(e), None
      if params.sha256 and sha256 != params.sha256.lower():
        raise ActionResult(35003, f"SHA-256 mismatch: {params.sha256}", None)
    elif params.type == "data":
      def write_file() -> None:
        nonlocal sha256
        sha256 = hashlib.sha256(data).hexdigest()
        if params.sha256 and sha256 != params.sha256.lower():
          raise ActionResult(35003, f"SHA-256 mismatch: {params.sha256}", None)
        with open(file_path, "wb") as f:
          f.write(params.data)
      try:
        file_path = os.path.join(self.__dir, str(id))
        await to_thread(write_file)
      except OSError as e:
        return 32000, str(e), None
    else:
      return 10004, f"Unsupported upload type {params.type}", None
    async with AsyncSession(self.__engine) as session:
      session.add(File(
        id=id,
        type=params.type,
        name=params.name,
        path=file_path,
        time=time,
        sha256=sha256,
        meta=metadata,
      ))
      await session.commit()
    return 0, "", UploadFileResult(file_id=str(id))

  async def get_file(
    self,
    params: GetFileParam,
    _bot_self: Optional[BotSelf] = None,
  ) -> ActionResultTuple[GetFileResult]:
    if params.type not in ("path", "url", "data"):
      return 10004, f"Invaild file type: {params.type}", None
    try:
      id = UUID(params.file_id)
    except ValueError:
      return 10003, f"Bad file id: {params.file_id}", None
    async with AsyncSession(self.__engine) as session:
      result = await session.execute(select(File).where(File.id == id))
    if not result:
      return 35004, f"File not exist: {params.file_id}", None
    file = cast(File, result.scalar())
    if file.type == "url":
      if params.type == "url":
        meta = URLFileMetadata.parse_obj(json.loads(file.meta))
        return 0, "", GetFileURLResult(
          name=file.name,
          sha256=file.sha256,
          url=meta.url,
          headers=meta.headers,
        )
      if not os.path.isfile(file.path):
        def write_file() -> None:
          if (sha256 := hashlib.sha256(data).hexdigest()) != file.sha256:
            raise ActionResult(33001, f"URL file SHA-256 have been changed to {sha256}", None)
          with open(file.path, "wb") as f:
            f.write(data)
        try:
          meta = URLFileMetadata.parse_obj(json.loads(file.meta))
          async with self.__http.get(meta.url, headers=meta.headers) as response:
            data = await response.read()
        except ClientError as e:
          return 33000, str(e), None
        try:
          await to_thread(write_file)
        except OSError as e:
          return 32000, str(e), None
    elif not os.path.isfile(file.path):
      async with AsyncSession(self.__engine) as session:
        await session.delete(file)
      return 32001, f"File is gone: {params.file_id}", None
    if params.type == "url":
      return 0, "", GetFileURLResult(
        name=file.name,
        sha256=file.sha256,
        url="file://" + file.path,
        headers={},
      )
    elif params.type == "path":
      return 0, "", GetFilePathResult(
        name=file.name,
        sha256=file.sha256,
        path=file.path,
      )
    else:
      def read_file() -> bytes:
        with open(file.path, "rb") as f:
          return f.read()
      try:
        data = await to_thread(read_file)
      except OSError as e:
        return 32000, str(e), None
      return 0, "", GetFileDataResult(
        name=file.name,
        sha256=file.sha256,
        data=data,
      )

  async def delete_file(
    self,
    params: DeleteFileParam,
    _bot_self: Optional[BotSelf],
  ) -> ActionResultTuple[DeleteFileResult]:
    async with AsyncSession(self.__engine) as session:
      result = await session.execute(select(File).where(File.id == id))
      if not result:
        return 35004, f"File not exist: {params.file_id}", None
      file = cast(File, result.scalar())
      if os.path.commonpath([file.path, self.dir]) == self.dir and os.path.isfile(file.path):
        try:
          os.remove(file.path)
        except OSError as e:
          return 32000, f"Failed to delete file: {e}", None
      await session.delete(file)
    return 0, "", DeleteFileResult()

  async def store_path(
    self,
    id: UUID,
    path: str,
    name: str = "",
    time: Optional[datetime] = None,
    sha256: Optional[str] = None,
  ) -> File:
    if sha256 is None:
      sha256 = await to_thread(calc_file_sha256, path)
    file = File(
      id=id,
      type="path",
      name=name or os.path.basename(path),
      path=path,
      time=time or datetime.now(),
      sha256=sha256,
      meta="",
    )
    async with AsyncSession(self.__engine) as session:
      session.add(file)
      await session.commit()
    return file
