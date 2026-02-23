from pydantic import TypeAdapter
from typing_extensions import TypedDict

from idhagnbot.http import get_session
from idhagnbot.plugins.bilibili_check.common import CONFIG


class VTBInfo(TypedDict):
  mid: int
  uname: str
  roomid: int


VTBInfosAdapter = TypeAdapter(list[VTBInfo])


def get_id() -> str:
  return "vtb"


def get_name() -> str:
  return "VTB"


def get_command() -> str:
  return "查单推"


def get_description() -> str:
  return "我超，□批！"


async def get_uids() -> set[int]:
  async with get_session().get(str(CONFIG().vtbs_api)) as response:
    infos = VTBInfosAdapter.validate_json(await response.text())
  return {info["mid"] for info in infos}
