from binascii import crc32
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cached_property

from arclet.entari import MessageChain, Session
from PIL import Image
from satori import Emoji


@dataclass
class Color:
    name: int
    avatar: int


COLORS = [
    Color(0xEF9A9A, 0xD32F2F),
    Color(0xF48FB1, 0xC2185B),
    Color(0xCE93D8, 0x7B1FA2),
    Color(0xB39DDB, 0x512DA8),
    Color(0x9FA8DA, 0x303F9F),
    Color(0x90CAF9, 0x1976D2),
    Color(0x81D4FA, 0x0288D1),
    Color(0x80DEEA, 0x0097A7),
    Color(0x80CBC4, 0x00796B),
    Color(0xA5D6A7, 0x388E3C),
    Color(0xC5E1A5, 0x689F38),
    Color(0xE6EE9C, 0xAFB42B),
    Color(0xFFF59D, 0xFBC02D),
    Color(0xFFE082, 0xFFA000),
    Color(0xFFCC80, 0xF57C00),
    Color(0xFFAB91, 0xE64A19),
]


@dataclass
class MessageInfo:
    user_id: str
    message: MessageChain


@dataclass
class SplitedMessageInfo:
    user_id: str
    message: list[MessageChain | Image.Image]


@dataclass
class UserInfo:
    user_id: str
    name: str
    avatar: str

    @cached_property
    def color(self) -> Color:
        return COLORS[crc32(self.user_id.encode()) % len(COLORS)]


MESSAGE_PROCESSOR_REGISTRY: dict[
    str,
    Callable[[Session, MessageChain], Awaitable[MessageChain]],
] = {}
EMOJI_REGISTRY: dict[str, Callable[[Session, Emoji], Awaitable[Image.Image]]] = {}
