import asyncio
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, Protocol, cast

import anyio
from aiohttp import ClientError, StreamReader
from arclet.alconna._internal._util import levenshtein
from arclet.entari import At, Author, Image, Member, Session, Text, User
from satori import select
from satori.exception import ActionFailed

from idhagnbot.http import get_session

type MemeParam = Text | Image | At
MAX_SIZE = 10485760


if TYPE_CHECKING:
    from ty_extensions import Intersection

    class WithUser(Protocol):
        user: User

    type MemberWithUser = Intersection[Member, WithUser]
else:
    MemberWithUser = Member


def validate_member_with_user(member: Member) -> MemberWithUser:
    if member.user:
        return cast("MemberWithUser", member)
    raise ValueError("Member has no user")


@dataclass
class MemeImage:
    image: bytes
    name: str
    gender: str


async def get_members(session: Session) -> list[MemberWithUser]:
    if not session.event.guild:
        return []
    try:
        members = await session.guild_member_list()
        return [validate_member_with_user(member) for member in members.list]
    except ActionFailed:
        return []


async def get_member(session: Session, user_id: str) -> MemberWithUser | None:
    if not session.event.guild:
        return None
    try:
        return validate_member_with_user(await session.guild_member_get(user_id))
    except ActionFailed:
        return None


async def get_user(session: Session, user_id: str) -> User | None:
    try:
        return await session.user_get(user_id)
    except ActionFailed:
        return None


async def fuzzy_get_member(
    session: Session,
    criterion: str,
    threshold: float = 0.8,
) -> MemberWithUser | None:
    matches = list[tuple[MemberWithUser, float]]()
    for member in await get_members(session):
        if (
            member.nick is not None
            and (score := levenshtein(member.nick, criterion)) >= threshold
        ):
            matches.append((member, score))
        if (
            member.user.nick is not None
            and (score := levenshtein(member.user.nick, criterion)) >= threshold
        ):
            matches.append((member, score))
        if (
            member.user.name is not None
            and (score := levenshtein(member.user.name, criterion)) >= threshold
        ):
            matches.append((member, score))
        if (
            member.user.id is not None
            and (score := levenshtein(member.user.id, criterion)) >= threshold
        ):
            matches.append((member, score))
    if not matches:
        return None
    return max(matches, key=lambda x: x[1])[0]


class FetchError(ValueError):
    message: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def read_max(content: StreamReader) -> bytes:
    buffer = BytesIO()
    async for chunk in content.iter_any():
        buffer.write(chunk)
        if buffer.tell() > MAX_SIZE:
            raise FetchError("图片过大")
    return buffer.getvalue()


async def user_fetch(session: Session, user_id: str) -> tuple[bytes, str, str]:
    if user_id == "自己":
        user_id = session.user.id
    elif user_id == "机器人":
        user_id = session.account.self_id
    if member := await get_member(session, user_id):
        nick = member.nick or member.user.nick or member.user.name or member.user.id
        avatar = member.user.avatar
    elif user := await get_user(session, user_id):
        nick = user.nick or user.name or user.id
        avatar = user.avatar
    elif member := await fuzzy_get_member(session, user_id):
        nick = member.nick or member.user.nick or member.user.name or member.user.id
        avatar = member.user.avatar
    else:
        raise FetchError(f"找不到成员 {user_id} 或平台不支持")
    if not avatar:
        raise FetchError(f"成员 {nick} 没有头像")
    if avatar.startswith("file://"):
        async with await anyio.Path.from_uri(avatar).open("rb") as f:
            data = await f.read(MAX_SIZE)
            if len(data) >= MAX_SIZE:
                raise FetchError("图片过大")
    else:
        async with get_session().get(session.account.ensure_url(avatar)) as response:
            data = await read_max(response.content)
    # Satori 的 User 没有 gender
    return data, nick, "unknown"


@dataclass
class FetchImage:
    image: MemeImage | None = None


async def handle_params(
    params: Iterable[MemeParam],
    session: Session,
    min_images: int,
) -> tuple[list[str], list[MemeImage]]:
    texts: list[str] = []
    images: list[FetchImage] = []
    names: list[str] = []

    async def fetch_image_and_update(image: Image, container: FetchImage) -> None:
        try:
            async with get_session().get(
                session.account.ensure_url(image.src),
            ) as response:
                data = await read_max(response.content)
        except ClientError as e:
            raise FetchError("无法下载图片") from e
        container.image = MemeImage(data, "", "unknown")

    async def fetch_user_and_update(user_id: str, container: FetchImage) -> None:
        image, nick, gender = await user_fetch(session, user_id)
        container.image = MemeImage(image, nick, gender)

    async with asyncio.TaskGroup() as tg:
        if session.reply:
            reply_images = select(session.reply.origin.message, Image)
            if reply_images:
                for image in reply_images:
                    container = FetchImage()
                    images.append(container)
                    tg.create_task(fetch_image_and_update(image, container))
            else:
                reply_author = select(session.reply.quote.children, Author)
                container = FetchImage()
                images.append(container)
                tg.create_task(fetch_user_and_update(reply_author[0].id, container))

        for param in params:
            if isinstance(param, Image):
                container = FetchImage()
                images.append(container)
                tg.create_task(fetch_image_and_update(param, container))
            elif isinstance(param, At):
                if param.id:
                    container = FetchImage()
                    images.append(container)
                    tg.create_task(fetch_user_and_update(param.id, container))
            elif param.text == "自己":
                container = FetchImage()
                images.append(container)
                tg.create_task(fetch_user_and_update(session.user.id, container))
            elif param.text == "机器人":
                container = FetchImage()
                images.append(container)
                tg.create_task(
                    fetch_user_and_update(session.account.self_id, container),
                )
            elif param.text.startswith("@"):
                container = FetchImage()
                images.append(container)
                tg.create_task(fetch_user_and_update(param.text[1:], container))
            elif param.text.startswith("#"):
                names.append(param.text)
            else:
                texts.append(param.text)

        if min_images == 2:
            if len(images) == 1:
                # 当所需图片数为 2 且已指定图片数为 1 时，使用发送者的头像作为第一张图
                container = FetchImage()
                images.insert(0, container)
                tg.create_task(fetch_user_and_update(session.user.id, container))
            elif len(images) == 0:
                # 当所需图片数为 2 且没有已指定图片时，使用发送者和机器人的头像
                container = FetchImage()
                images.append(container)
                tg.create_task(fetch_user_and_update(session.user.id, container))
                container = FetchImage()
                images.append(container)
                tg.create_task(
                    fetch_user_and_update(session.account.self_id, container),
                )
        elif min_images == 1 and len(images) == 0:
            # 当所需图片数为 1 且没有已指定图片时，使用发送者的头像
            container = FetchImage()
            images.append(container)
            tg.create_task(fetch_user_and_update(session.user.id, container))

    valid_images = [image.image for image in images if image.image]
    for name, image in zip(names, valid_images, strict=False):
        image.name = name

    return texts, valid_images


def flatten_exception_group[T: BaseException](
    excgroup: BaseExceptionGroup[T],
) -> Generator[T]:
    for exc in excgroup.exceptions:
        if isinstance(exc, BaseExceptionGroup):
            yield from flatten_exception_group(exc)  # ty:ignore[invalid-argument-type]
        else:
            yield exc
