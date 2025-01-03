from typing import Optional

import aiohttp
import nonebot

__all__ = ["get_session"]
_session: Optional[aiohttp.ClientSession] = None
_driver = nonebot.get_driver()


def get_session() -> aiohttp.ClientSession:
  global _session
  if _session is None:
    _session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar())
  return _session


@_driver.on_shutdown
async def on_shutdown():
  if _session:
    await _session.close()
