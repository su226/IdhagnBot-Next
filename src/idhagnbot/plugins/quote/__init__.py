import asyncio
import random
from collections.abc import Awaitable, Sequence
from itertools import dropwhile, islice
from uuid import UUID, uuid4

from anyio import Path
from arclet.alconna import Alconna, Args, CommandMeta
from arclet.entari import Image as ImageSeg
from arclet.entari import MessageChain, Session, Text, command, local_data
from arclet.letoderea import propagate
from entari_plugin_database import AsyncSession, Base  # entari: plugin
from entari_plugin_permission import require_permission
from PIL import Image
from satori import Emoji
from satori import select as satori_select
from satori.element import Br
from sqlalchemy import select
from sqlalchemy.orm import Mapped, aliased, mapped_column

from idhagnbot import text
from idhagnbot.asyncio import gather_map, gather_seq
from idhagnbot.color import split_rgb
from idhagnbot.image import (
    SCALE_RESAMPLE,
    apply_circle_mask,
    apply_rounded_rectangle_mask,
    contain_down,
    open_url,
    paste,
    replace,
    to_segment,
)
from idhagnbot.plugins.quote.common import (
    EMOJI_REGISTRY,
    MESSAGE_PROCESSOR_REGISTRY,
    MessageInfo,
    SplitedMessageInfo,
    UserInfo,
)
from idhagnbot.plugins.quote.onebot import register as register_onebot
from idhagnbot.plugins.record import Message, MessageRevision

register_onebot()


class SentQuote(Base):
    __tablename__ = "idhagnbot_quote_sent_quote"
    platform: Mapped[str] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(primary_key=True)
    quote_id: Mapped[UUID]


def get_dirname(platform: str, channel_id: str) -> Path:
    return Path(
        local_data.get_data_dir("idhagnbot")
        / "quote"
        / platform.replace(":", "_")
        / channel_id.replace(":", "_"),
    )


def generate_avatar(info: UserInfo) -> Image.Image:
    im = Image.new("RGB", (64, 64), split_rgb(info.color.avatar))
    text.paste(
        im,
        (32, 32),
        info.avatar[9:],
        "sans",
        32,
        anchor=(0.5, 0.5),
        color=0xFFFFFF,
    )
    apply_circle_mask(im)
    return im


def avatar_process(im: Image.Image) -> Image.Image:
    im = im.resize((64, 64), SCALE_RESAMPLE)
    apply_circle_mask(im)
    return im


async def fetch_avatar(info: UserInfo) -> Image.Image:
    if info.avatar.startswith("avatar://"):
        return await asyncio.to_thread(generate_avatar, info)
    return await open_url(info.avatar, avatar_process)


async def fetch_avatars(users: dict[str, UserInfo]) -> dict[str, Image.Image]:
    return await gather_map(
        {user_id: fetch_avatar(info) for user_id, info in users.items()},
    )


async def split_one(session: Session, message: MessageInfo) -> SplitedMessageInfo:
    tasks: list[MessageChain | asyncio.Task[Image.Image]] = []
    async with asyncio.TaskGroup() as tg:
        elements = MessageChain()
        for element in message.message:
            if isinstance(element, ImageSeg):
                if elements:
                    tasks.append(elements)
                    elements = MessageChain()
                tasks.append(
                    tg.create_task(
                        open_url(str(session.account.ensure_url(element.src))),
                    ),
                )
            else:
                elements.append(element)
        if elements:
            tasks.append(elements)
            elements = MessageChain()
    return SplitedMessageInfo(
        message.user_id,
        [task.result() if isinstance(task, asyncio.Task) else task for task in tasks],
    )


async def split_images(
    session: Session,
    messages: Sequence[MessageInfo],
) -> list[SplitedMessageInfo]:
    return await gather_seq(split_one(session, message) for message in messages)


async def fetch_emoji(session: Session, emoji: Emoji) -> Image.Image | None:
    platform_fetch = EMOJI_REGISTRY.get(session.account.platform)
    if platform_fetch:
        return await platform_fetch(session, emoji)
    images = satori_select(emoji.children, ImageSeg)
    if images:
        return await open_url(str(session.account.ensure_url(images[0].src)))
    return None


async def fetch_emojis(
    session: Session,
    messages: Sequence[MessageInfo],
) -> dict[str, Image.Image]:
    tasks: dict[str, Awaitable[Image.Image | None]] = {}
    for message in messages:
        for emoji in message.message[Emoji]:
            if emoji.id not in tasks:
                tasks[emoji.id] = fetch_emoji(session, emoji)
    emojis = await gather_map(tasks)
    return {k: v for k, v in emojis.items() if v}


def render_content(
    message: list[MessageChain | Image.Image],
    emojis: dict[str, Image.Image],
    user: UserInfo | None,
) -> Image.Image:
    rows = list[Image.Image]()
    if user:
        rows.append(text.render(user.name, "sans bold", 32, color=user.color.name))

    for row in message:
        if isinstance(row, Image.Image):
            rows.append(contain_down(row, (640, 640)))
        else:
            buffer = text.RichText()
            buffer.set_font("sans", 32)
            buffer.set_width(640)
            for segment in row:
                if isinstance(segment, Text):
                    buffer.append(segment.text)
                elif isinstance(segment, Br):
                    buffer.append("\n")
                elif isinstance(segment, Emoji):
                    if segment.id in emojis:
                        buffer.append_image(emojis[segment.id])
                    else:
                        buffer.append("[emoji]")
                else:
                    buffer.append(f"[{segment.tag}]")
            rows.append(buffer.render(0xFFFFFF))
    padding = 24
    width = max(im.width for im in rows) + padding * 2
    height = sum(im.height for im in rows) + padding * 2
    out_im = Image.new("RGB", (width, height), (45, 37, 55))
    y = padding
    for im in rows:
        paste(out_im, im, (padding, y))
        y += im.height
    apply_rounded_rectangle_mask(out_im, 32)
    return out_im


async def render_chat(
    session: Session,
    messages: Sequence[MessageInfo],
    users: dict[str, UserInfo],
) -> Image.Image:
    avatars, splited, emojis = await asyncio.gather(
        fetch_avatars(users),
        split_images(session, messages),
        fetch_emojis(session, messages),
    )

    def make() -> Image.Image:
        nonlocal emojis
        emojis = {
            emoji_id: emoji.resize((40, 40), SCALE_RESAMPLE)
            for emoji_id, emoji in emojis.items()
        }
        contents = [
            render_content(
                message.message,
                emojis,
                users[message.user_id]
                if i == 0 or messages[i - 1].user_id != message.user_id
                else None,
            )
            for i, message in enumerate(splited)
        ]
        avatar_size = 64
        gap = 16
        gap_small = 4
        width = max(im.width for im in contents) + avatar_size + gap
        height = sum(im.height for im in contents)
        for i, message in enumerate(messages):
            if i != 0:
                height += (
                    gap if message.user_id != messages[i - 1].user_id else gap_small
                )
        out_im = Image.new("RGBA", (width, height))
        y = 0
        for i, (message, im) in enumerate(zip(messages, contents, strict=True)):
            replace(out_im, im, (avatar_size + gap, y))
            y += im.height
            if i == len(messages) - 1 or messages[i + 1].user_id != message.user_id:
                replace(out_im, avatars[message.user_id], (0, y), (0, 1))
                y += gap
            else:
                y += gap_small
        return out_im

    return await asyncio.to_thread(make)


async def process_message(session: Session, message: MessageInfo) -> MessageInfo:
    name = session.account.platform
    if name in MESSAGE_PROCESSOR_REGISTRY:
        message.message = await MESSAGE_PROCESSOR_REGISTRY[name](
            session,
            message.message,
        )
    return message


async def get_user_info(session: Session, user_id: str) -> tuple[str, UserInfo]:
    if session.event.guild:
        member = await session.guild_member_get(user_id)
        if not member.user:
            raise ValueError("Member has no user")
        user_id = member.user.id
        nick = member.nick or member.user.nick or member.user.name or member.user.id
        avatar = member.avatar or member.user.avatar
    else:
        user = await session.user_get(user_id)
        user_id = user.id
        nick = user.nick or user.name or user.id
        avatar = user.avatar
    if avatar:
        avatar = str(session.account.ensure_url(avatar))
    else:
        avatar = f"avatar://{nick[0]}"
    user_info = UserInfo(user_id, nick, avatar)
    return user_id, user_info


@command.mount(
    Alconna("q", Args["count", int, 1], meta=CommandMeta("引用消息，aka. 入典")),
)
@propagate(require_permission("idhagnbot.quote.quote", prompt=True))
async def handle_quote(session: Session, db: AsyncSession, count: int) -> None:
    if not session.reply:
        await session.send("请回复一条消息")
        return
    if count < 1 or count > 10:
        await session.send("只能引用 1 至 10 条消息")
        return
    start_from = await db.get(
        MessageRevision,
        (session.account.platform, session.channel.id, session.reply.origin.id, 1),
    )
    if not start_from:
        await session.send("引用的消息过于久远")
        return
    records = await db.execute(
        select(
            Message.id,
            Message.user_id,
            (current_revision := aliased(MessageRevision)).content,
        )
        .join(
            first_revision := aliased(MessageRevision),
            (Message.platform == first_revision.platform)
            & (Message.channel_id == first_revision.channel_id)
            & (Message.id == first_revision.message_id)
            & (first_revision.revision == 1),
        )
        .join(
            current_revision,
            (Message.platform == current_revision.platform)
            & (Message.channel_id == current_revision.channel_id)
            & (Message.id == current_revision.message_id)
            & (Message.current_revision == current_revision.revision),
        )
        .where(
            Message.platform == session.account.platform,
            Message.channel_id == session.channel.id,
            first_revision.created_at >= start_from.created_at,
            current_revision.deleted_at.is_(None),
        )
        # 如果平台时间戳为浮点型，几乎不会出现相同时间戳的情况
        # 但如果时间戳为整型，则可能出现相同时间戳，因此预留一定余量
        .order_by(first_revision.created_at)
        .limit(count + 10),
    )
    records = list(
        islice(dropwhile(lambda x: x[0] != start_from.message_id, records), count),
    )
    messages = [MessageInfo(x[1], MessageChain.of(x[2])) for x in records]
    user_ids = {x[1] for x in records}
    messages, users = await asyncio.gather(
        gather_seq(process_message(session, message) for message in messages),
        gather_seq(get_user_info(session, user_id) for user_id in user_ids),
    )
    im = await render_chat(session, messages, dict(users))
    dirname = get_dirname(session.account.platform, session.channel.id)
    await dirname.mkdir(parents=True, exist_ok=True)
    quote_id = uuid4()
    await asyncio.to_thread(im.save, dirname / f"{quote_id}.png")
    receipts = await session.send([to_segment(im)])
    for receipt in receipts:
        db.add(
            SentQuote(
                platform=session.account.platform,
                channel_id=session.channel.id,
                message_id=receipt.id,
                quote_id=quote_id,
            ),
        )
    await db.commit()


@command.mount(Alconna("qrand", meta=CommandMeta("随机引用")))
@propagate(require_permission("idhagnbot.quote.random", prompt=True))
async def handle_random(session: Session, db: AsyncSession) -> None:
    dirname = get_dirname(session.account.platform, session.channel.id)
    await dirname.mkdir(parents=True, exist_ok=True)
    files = [x async for x in dirname.iterdir()]
    if not files:
        await session.send("暂时没有引用")
        return
    file = random.choice(files)
    quote_id = UUID(file.stem)
    receipts = await session.send([ImageSeg.of(path=str(file))])
    for receipt in receipts:
        db.add(
            SentQuote(
                platform=session.account.platform,
                channel_id=session.channel.id,
                message_id=receipt.id,
                quote_id=quote_id,
            ),
        )
    await db.commit()


@command.on(Alconna("qd", meta=CommandMeta("删除引用")))
@propagate(require_permission("idhagnbot.quote.delete", prompt=True))
async def handle_delete(session: Session, db: AsyncSession) -> str:
    if not session.reply:
        return "请回复一条引用图片"
    sent_quote = await db.get(
        SentQuote,
        (session.account.platform, session.channel.id, session.reply.quote.id),
    )
    if not sent_quote:
        return "请回复一条引用图片"
    dirname = get_dirname(session.account.platform, session.channel.id)
    filename = dirname / f"{sent_quote.quote_id}.png"
    await filename.unlink(missing_ok=True)
    return "已删除当前引用"
