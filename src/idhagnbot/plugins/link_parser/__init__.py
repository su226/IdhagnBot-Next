import asyncio
import json
from collections.abc import Generator
from importlib.util import find_spec
from itertools import chain
from typing import Any

from arclet.entari import (
    Account,
    MessageChain,
    MessageCreatedEvent,
    Session,
    Text,
    metadata,
    plugin_config,
)
from arclet.entari import Image as ImageSeg
from arclet.letoderea import BLOCK, Contexts, ExitState, enter_if, on
from entari_plugin_database import AsyncSession, Base
from loguru import logger
from PIL import Image
from pydantic import BaseModel
from satori import Element
from satori.element import Br
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.asyncio import gather_seq
from idhagnbot.image import open_url
from idhagnbot.plugins.link_parser.common import Content
from idhagnbot.plugins.link_parser.contents import (
    bilibili_activity,
    bilibili_b23,
    bilibili_video,
    github,
)
from idhagnbot.url import extract_url


class Config(BaseModel):
    qrcode: bool = False


metadata("", config=Config)
CONFIG = plugin_config(Config)
CONTENTS: list[Content[Any]] = [bilibili_activity, bilibili_b23, bilibili_video, github]
cv2_warned = False


class LastState(Base):
    __tablename__ = "idhagnbot_link_parser_last_state"
    platform: Mapped[str] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(primary_key=True)
    last_state: Mapped[str]


def extract_links(message: MessageChain[Element]) -> Generator[str]:
    for segment in message:
        if segment.tag == "onebot:json":
            data = json.loads(segment["data"])
            try:
                yield data["meta"]["detail_1"]["qqdocurl"]
            except KeyError:
                pass
            try:
                yield data["meta"]["news"]["jumpUrl"]
            except KeyError:
                pass
        elif isinstance(segment, Text):
            yield from extract_url(segment.text)


def decode(im: Image.Image) -> list[str]:
    import cv2
    import numpy as np

    _retval, decoded_info, _points, _straight_code = (
        cv2.QRCodeDetector().detectAndDecodeMulti(np.asarray(im))
    )
    return [data for data in decoded_info if data.startswith(("http://", "https://"))]


async def download_and_decode(account: Account, image: ImageSeg) -> list[str]:
    im = await open_url(str(account.ensure_url(image.src)))
    return await asyncio.to_thread(decode, im)


async def extract_qrcodes(session: Session) -> list[str]:
    if find_spec("cv2") is None:
        global cv2_warned
        if not cv2_warned:
            logger.warning(
                "未安装 OpenCV，无法识别二维码。如需安装，请将 "
                "idhagnbot[cv2] 添加到依赖中。",
            )
            cv2_warned = True
        return []
    return list(
        chain.from_iterable(
            await gather_seq(
                download_and_decode(session.account, seg)
                for seg in session.elements[ImageSeg]
            ),
        ),
    )


async def check_links(ctx: Contexts, db: AsyncSession, session: Session) -> bool:
    links = set(extract_links(session.elements))
    if CONFIG.qrcode:
        links.update(await extract_qrcodes(session))
    platform = session.account.platform
    channel_id = session.channel.id
    last = await db.get(LastState, (platform, channel_id))
    last = json.loads(last.last_state) if last else dict[str, Any]()
    matched = False
    for link in links:
        results = await gather_seq(
            content.match_link(link, last) for content in CONTENTS
        )
        for content, result in zip(CONTENTS, results, strict=True):
            if result.matched:
                if matched:
                    ctx["multiple"] = True
                    return matched
                ctx["content"] = content
                ctx["state"] = result.state
                ctx["multiple"] = False
                matched = True
                break
    return matched


@on(MessageCreatedEvent, priority=101)
@enter_if(check_links)
async def handle_links(ctx: Contexts, db: AsyncSession, session: Session) -> ExitState:
    result = await ctx["content"].format_link(ctx["state"])
    platform = session.account.platform
    channel_id = session.channel.id
    current = await db.get(LastState, (platform, channel_id))
    if current:
        current.last_state = json.dumps(result.state)
        db.add(current)
    else:
        db.add(
            LastState(
                platform=platform,
                channel_id=channel_id,
                last_state=json.dumps(result.state),
            ),
        )
    await db.commit()
    if ctx["multiple"]:
        result.message += Br()
        result.message += Text("⚠发现多个可解析链接，结果仅包含第一个")
    await session.send(result.message)
    return BLOCK
