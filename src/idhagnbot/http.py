import aiohttp
import nonebot

__all__ = ["BROWSER_UA", "get_session"]
_session: aiohttp.ClientSession | None = None
_driver = nonebot.get_driver()
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0"


def get_session() -> aiohttp.ClientSession:
  global _session
  if _session is None:
    _session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar())
  return _session


@_driver.on_shutdown
async def on_shutdown() -> None:
  if _session:
    await _session.close()
