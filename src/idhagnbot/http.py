from aiohttp import ClientSession

from idhagnbot.support import current_entari

__all__ = ["BROWSER_UA", "get_session"]
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0"


def get_session() -> ClientSession:
    return current_entari().http
