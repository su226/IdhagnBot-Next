from base64 import urlsafe_b64decode
from collections.abc import Sequence

from arclet.entari import Element, Image
from yarl import URL

from idhagnbot.plugins.repeat.common import COMPARATOR_REGISTRY


def _extract_image_hash(raw_url: str) -> str:
    # internal?
    if not raw_url.startswith(("http://", "https://")):
        return raw_url
    url = URL(raw_url)
    if url.host == "gchat.qpic.cn" and url.path.startswith("/gchatpic_new"):
        return url.parts[3].split("-", 2)[2].casefold()  # MD5
    if url.host == "multimedia.nt.qq.com.cn" and url.path.startswith("/download"):
        return urlsafe_b64decode(url.query["fileid"] + "==")[2:22].hex()  # SHA1
    return raw_url


def comparator(a: Sequence[Element], b: Sequence[Element]) -> bool:
    if len(a) != len(b):
        return False
    for seg1, seg2 in zip(a, b, strict=True):
        if isinstance(seg1, Image) and isinstance(seg2, Image):
            hash_a = _extract_image_hash(seg1.src)
            hash_b = _extract_image_hash(seg2.src)
            if hash_a != hash_b:
                return False
        elif seg1 != seg2:
            return False
    return True


def register() -> None:
    COMPARATOR_REGISTRY["onebot"] = comparator
