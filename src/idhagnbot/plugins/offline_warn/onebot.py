import time
from typing import Literal, Union

import nonebot
from nonebot import logger
from nonebot.adapters.onebot.v11 import Adapter, NoticeEvent

from idhagnbot.plugins.offline_warn.common import queue_message


class NapCatOfflineEvent(NoticeEvent):
  notice_type: Literal["bot_offline"]
  user_id: int
  tag: str
  message: str


class LagrangeOfflineEvent(NoticeEvent):
  notice_type: Literal["notify"]
  sub_type: Literal["bot_offline"]
  tag: str
  message: str


Adapter.add_custom_model(NapCatOfflineEvent)
Adapter.add_custom_model(LagrangeOfflineEvent)


offline = nonebot.on_type((NapCatOfflineEvent, LagrangeOfflineEvent))


@offline.handle()
async def handle_offline(event: Union[NapCatOfflineEvent, LagrangeOfflineEvent]) -> None:
  now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event.time))
  tag = event.tag
  message = event.message
  prefix = f"后端 OneBot V11 {event.self_id} 在 {now_str} 左右下线，{tag=} {message=}"
  logger.warning(prefix + "，将发送警告！")
  await queue_message(prefix + "，请注意！")
