from arclet.entari import Image as ImageSeg
from arclet.entari import MessageChain, Session
from PIL import Image
from satori import Emoji
from yarl import URL

from idhagnbot.image import open_url
from idhagnbot.onebot import get_rkey_cached
from idhagnbot.plugins.quote.common import EMOJI_REGISTRY, MESSAGE_PROCESSOR_REGISTRY


async def process_message(session: Session, message: MessageChain) -> MessageChain:
    if ImageSeg in message:
        rkeys = await get_rkey_cached(session.account)
        rkey = rkeys.group if session.event.guild is not None else rkeys.private
        for image in message[ImageSeg]:
            image.src = str(URL(image.src).update_query(rkey=rkey.rkey))
    return message


async def fetch_emoji(session: Session, emoji: Emoji) -> Image.Image:
    return await open_url(f"https://koishi.js.org/QFace/static/s{emoji.id}.png")


def register() -> None:
    MESSAGE_PROCESSOR_REGISTRY["onebot"] = process_message
    EMOJI_REGISTRY["onebot"] = fetch_emoji
