from base64 import b64decode
from datetime import datetime
from typing import Literal

from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA256
from pydantic import TypeAdapter
from typing_extensions import TypedDict

from idhagnbot.http import get_session


class Meta(TypedDict):
  lastUpdated: datetime


class User(TypedDict):
  uid: str
  name: str
  avatar: str
  birthday: str
  followers: int
  likes: int
  playCount: int
  lastUpdated: datetime


class Users(TypedDict):
  meta: Meta
  users: list[User]


UsersAdapter = TypeAdapter(Users)


class Encrypted(TypedDict):
  encrypted: Literal[True]
  algorithm: Literal["AES-256-GCM"]
  v: Literal[2]
  kdf: Literal["HMAC-SHA256"]
  context: str
  iv: str
  data: str


def decrypt(encrypted: Encrypted) -> bytes:
  key = HMAC.new(
    HMAC_KEY,
    f"FurUp:data:key:v1:{encrypted['context']}".encode(),
    digestmod=SHA256,
  ).digest()
  nonce = b64decode(encrypted["iv"])
  aes = AES.new(key, AES.MODE_GCM, nonce)
  aes.update(encrypted["context"].encode())
  data = b64decode(encrypted["data"])
  data, mac = data[:-16], data[-16:]
  return aes.decrypt_and_verify(data, mac)


HMAC_KEY = b64decode("Gc2qEc8Gtxcyf7od8n9u95AHERiyZyI/K0czfS6DpHc=")
EncryptedAdapter = TypeAdapter(Encrypted)


def get_id() -> str:
  return "furry"


def get_name() -> str:
  return "Furry"


def get_command() -> str:
  return "查福瑞"


def get_description() -> str:
  return "我超，福瑞控！"


async def get_uids() -> set[int]:
  async with get_session().get("https://furup.me/data/users.json") as response:
    encrypted = EncryptedAdapter.validate_json(await response.text())
  users = UsersAdapter.validate_json(decrypt(encrypted))
  return {int(user["uid"]) for user in users["users"]}
