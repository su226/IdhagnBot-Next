import asyncio
import math
from itertools import batched
from uuid import UUID, uuid4

from anyio import Path
from arclet import letoderea
from arclet.alconna import Alconna, Args, CommandMeta
from arclet.entari import Image as ImageSeg
from arclet.entari import (
    MessageChain,
    Session,
    command,
    filter_,
    local_data,
)
from entari_plugin_database import (
    AsyncSession,
    Base,
    Mapped,
    mapped_column,
    select,
)  # entari: plugin
from entari_plugin_permission import require_permission  # entari: plugin
from PIL import Image
from satori import Element
from sqlalchemy import UniqueConstraint

from idhagnbot.http import get_session
from idhagnbot.image import contain_down, paste, to_segment
from idhagnbot.plugins.redirect import GuildId
from idhagnbot.text import render


class Aspect(Base):
    __tablename__ = "idhagnbot_aspect_aspect"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    platform: Mapped[str]
    guild_id: Mapped[str]
    title: Mapped[str]
    __table_args__ = (UniqueConstraint("platform", "guild_id", "title"),)


COLUMNS = 5
IMAGE_SIZE = 100
TEXT_HEIGHT = 40
GAP = 10
MARGIN = 25
FONT_SIZE = 30
HEADER_FONT_SIZE = 50


@command.on(Alconna("群要素", meta=CommandMeta("查看当前的群要素")))
@letoderea.propagate(require_permission("idhagnbot.aspect.show", prompt=True))
@filter_.public
async def handle_show(
    platform_guild_id: GuildId,
    sql: AsyncSession,
) -> str | MessageChain:
    platform, guild_id = platform_guild_id
    result = await sql.scalars(
        select(Aspect).where(Aspect.platform == platform, Aspect.guild_id == guild_id),
    )
    aspects = result.all()

    if not aspects:
        return "还没有群要素"

    def make() -> ImageSeg:
        lines = math.ceil(len(aspects) / COLUMNS)
        header_im = render("群要素", "sans bold", HEADER_FONT_SIZE)
        width = MARGIN * 2 + max(
            header_im.width,
            COLUMNS * IMAGE_SIZE + (COLUMNS - 1) * MARGIN,
        )
        height = (
            MARGIN * 2
            + header_im.height
            + lines * (IMAGE_SIZE + GAP + TEXT_HEIGHT + MARGIN)
        )
        im = Image.new("RGB", (width, height), (255, 255, 255))
        paste(im, header_im, (width // 2, MARGIN), (0.5, 0))
        y = MARGIN * 2 + header_im.height
        image_dir = local_data.get_data_dir("idhagnbot") / "aspects"
        for line in batched(aspects, COLUMNS, strict=False):
            x = MARGIN
            for aspect in line:
                aspect_im = Image.open(image_dir / str(aspect.id))
                aspect_im = contain_down(aspect_im, (IMAGE_SIZE, IMAGE_SIZE))
                paste(
                    im,
                    aspect_im,
                    (x + IMAGE_SIZE // 2, y + IMAGE_SIZE // 2),
                    (0.5, 0.5),
                )
                title_im = render(aspect.title, "sans", FONT_SIZE)
                title_im = contain_down(title_im, (IMAGE_SIZE, TEXT_HEIGHT))
                paste(
                    im,
                    title_im,
                    (x + IMAGE_SIZE // 2, y + IMAGE_SIZE + GAP),
                    (0.5, 0),
                )
                x += IMAGE_SIZE + MARGIN
            y += IMAGE_SIZE + GAP + TEXT_HEIGHT + MARGIN
        return to_segment(im)

    return MessageChain(await asyncio.to_thread(make))


def get_reply_image(elements: list[Element]) -> ImageSeg | None:
    for element in elements:
        if isinstance(element, ImageSeg):
            return element
    return None


@command.on(
    Alconna(
        "添加群要素",
        Args["title", str],
        Args["image?", ImageSeg, None],
        meta=CommandMeta("又多了一个要素"),
    ),
)
@letoderea.propagate(require_permission("idhagnbot.aspect.add", prompt=True))
@filter_.public
async def handle_add(
    session: Session,
    db: AsyncSession,
    platform_guild_id: GuildId,
    title: str,
    image: ImageSeg | None,
) -> str:
    platform, guild_id = platform_guild_id
    if image:
        image_seg = image
    elif session.reply and (
        reply_image := get_reply_image(session.reply.quote.children)
    ):
        image_seg = reply_image
    else:
        return "没有传入图片"
    image_dir = Path(local_data.get_data_dir("idhagnbot") / "aspects")
    await image_dir.mkdir(parents=True, exist_ok=True)
    aspect_id = uuid4()
    path = image_dir / str(aspect_id)
    http = get_session()
    commited = False
    try:
        async with (
            http.get(session.account.ensure_url(image_seg.src)) as response,
            await path.open("wb") as f,
        ):
            async for chunk in response.content.iter_chunked(65536):
                await f.write(chunk)
        db.add(Aspect(id=aspect_id, platform=platform, guild_id=guild_id, title=title))
        await db.commit()
        commited = True
    finally:
        if not commited:
            await path.unlink(missing_ok=True)
    return "要素已添加"


@command.on(
    Alconna(
        "删除群要素",
        Args["title", str],
        meta=CommandMeta("为什么少了一个要素"),
    ),
)
@letoderea.propagate(require_permission("idhagnbot.aspect.remove", prompt=True))
@filter_.public
async def handle_remove(
    title: str,
    platform_guild_id: GuildId,
    db: AsyncSession,
) -> str:
    platform, guild_id = platform_guild_id
    aspect = await db.scalar(
        select(Aspect).where(
            Aspect.platform == platform,
            Aspect.guild_id == guild_id,
            Aspect.title == title,
        ),
    )
    if not aspect:
        return "要素不存在"
    await db.delete(aspect)
    await db.commit()
    path = local_data.get_data_dir("idhagnbot") / "aspects" / str(aspect.id)
    await Path(path).unlink(missing_ok=True)
    return "要素已删除"
