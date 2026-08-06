import asyncio
import base64
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from aiohttp import ClientError
from arclet.alconna import (
    Alconna,
    Args,
    Arparma,
    CommandMeta,
    MultiVar,
    Option,
    store_false,
    store_true,
)
from arclet.entari import (
    Image,
    MessageChain,
    Ready,
    Session,
    command,
    metadata,
    plugin_config,
)
from arclet.letoderea import on
from entari_plugin_permission import require_permission  # entari: plugin
from loguru import logger
from pydantic import BaseModel, HttpUrl, TypeAdapter

from idhagnbot.asyncio import gather_seq
from idhagnbot.http import get_session
from idhagnbot.meme_common import (
    FetchError,
    MemeImage,
    MemeParam,
    flatten_exception_group,
    handle_params,
)
from idhagnbot.nepattern import RangeFloat, RangeInt


class Config(BaseModel):
    base_url: HttpUrl | None = None


class ParserFlags(BaseModel):
    short: bool
    long: bool
    short_aliases: list[str]
    long_aliases: list[str]


class MemeOption(BaseModel):
    name: str
    description: str | None
    parser_flags: ParserFlags

    def names(self) -> str:
        short_aliases = self.parser_flags.short_aliases
        if self.parser_flags.short:
            short_aliases = [self.name[0], *short_aliases]
        long_aliases = self.parser_flags.long_aliases
        if self.parser_flags.long:
            long_aliases = [self.name, *long_aliases]
        names = list[str]()
        names.extend([f"-{flag}" for flag in short_aliases])
        names.extend([f"--{flag}" for flag in long_aliases])
        return "|".join(names)


class BooleanOption(MemeOption):
    type: Literal["boolean"]
    default: bool | None

    def option(self) -> Option:
        action = None
        if self.default is not None:
            action = store_false if self.default else store_true
        return Option(
            name=self.names(),
            dest=self.name,
            default=self.default,
            action=action,
            help_text=self.description,
        )


class StringOption(MemeOption):
    type: Literal["string"]
    default: str | None
    choices: list[str] | None

    def option(self) -> Option:
        arg_type = self.choices or str
        args = (
            Args[self.name, arg_type, self.default]
            if self.default
            else Args[self.name, arg_type]
        )
        return Option(
            name=self.names(),
            args=args,
            dest=self.name,
            help_text=self.description,
        )


class IntegerOption(MemeOption):
    type: Literal["integer"]
    default: int | None
    minimum: int | None
    maximum: int | None

    def option(self) -> Option:
        arg_type = (
            RangeInt(self.minimum, self.maximum)
            if self.minimum is not None or self.maximum is not None
            else int
        )
        args = (
            Args[self.name, arg_type, self.default]
            if self.default
            else Args[self.name, arg_type]
        )
        return Option(
            name=self.names(),
            args=args,
            dest=self.name,
            help_text=self.description,
        )


class FloatOption(MemeOption):
    type: Literal["float"]
    default: float | None
    minimum: float | None
    maximum: float | None

    def option(self) -> Option:
        arg_type = (
            RangeFloat(self.minimum, self.maximum)
            if self.minimum is not None or self.maximum is not None
            else float
        )
        args = (
            Args[self.name, arg_type, self.default]
            if self.default
            else Args[self.name, arg_type]
        )
        return Option(
            name=self.names(),
            args=args,
            dest=self.name,
            help_text=self.description,
        )


class MemeParams(BaseModel):
    min_images: int
    max_images: int
    min_texts: int
    max_texts: int
    default_texts: list[str]
    options: list[BooleanOption | StringOption | IntegerOption | FloatOption]


class MemeShortcut(BaseModel):
    pattern: str
    humanized: str | None
    names: list[str]
    texts: list[str]
    options: dict[str, bool | str | int | float]


class MemeInfo(BaseModel):
    key: str
    params: MemeParams
    keywords: list[str]
    shortcuts: list[MemeShortcut]
    tags: set[str]
    date_created: datetime
    date_modified: datetime


metadata("", config=Config)
CONFIG = plugin_config(Config)
memes = dict[str, MemeInfo]()


@on(Ready)
async def register_memes() -> None:
    if not CONFIG.base_url:
        return
    http = get_session()
    while True:
        try:
            async with http.get(
                f"{CONFIG.base_url}meme/infos",
                raise_for_status=True,
            ) as response:
                infos = TypeAdapter(list[MemeInfo]).validate_json(
                    await response.text(),
                )
                break
        except ClientError:
            logger.exception("初始化 meme_generator_rs 失败")
            await asyncio.sleep(10)
    for info in infos:
        memes[info.key] = info
        cmd = Alconna(
            info.keywords[0],
            *(opt.option() for opt in info.params.options),
            Args["meme_params", MultiVar(MemeParam, "*")],
            namespace="memes",
        )
        for keyword in info.keywords[1:]:
            cmd.shortcut(keyword, command=info.keywords[0])
        command.on(cmd)(MemeHandler(info.key).handle).propagate(
            require_permission(f"idhagnbot.meme_generator_rs.{info.key}", prompt=True),
        )
    command.on(
        Alconna(
            "随机梗图",
            Args["meme_params", MultiVar(MemeParam, "*")],
            meta=CommandMeta("制作符合参数数量的随机梗图"),
        ),
    )(handle_meme_random).propagate(
        require_permission("idhagnbot.meme_generator_rs.random", prompt=True),
    )


async def upload_image(image: MemeImage) -> dict[str, str]:
    payload = {"type": "data", "data": base64.b64encode(image.image).decode()}
    async with get_session().post(
        f"{CONFIG.base_url}image/upload",
        json=payload,
    ) as response:
        data = await response.json()
        return {"name": image.name, "id": data["image_id"]}


async def handle_meme_key(
    key: str,
    images: list[MemeImage],
    texts: list[str],
    args: dict[str, bool | str | int | float],
) -> str | MessageChain:
    payload = {
        "images": await gather_seq(upload_image(image) for image in images),
        "texts": texts,
        "options": args,
    }
    async with get_session().post(
        f"{CONFIG.base_url}memes/{key}",
        json=payload,
    ) as response:
        if response.status != 200:
            error = await response.json()
            return error["message"]
        data = await response.json()
        image_id = data["image_id"]
    async with get_session().get(f"{CONFIG.base_url}image/{image_id}") as response:
        data = await response.read()
        mime = response.content_type

    return MessageChain(Image.of(raw=data, mimetype=mime))


@dataclass
class MemeHandler:
    key: str

    async def handle(
        self,
        meme_params: tuple[MemeParam, ...],
        session: Session,
        arp: Arparma[Any],
    ) -> str | MessageChain:
        info = memes[self.key]

        try:
            texts, images = await handle_params(
                meme_params,
                session,
                info.params.min_images,
            )
        except BaseExceptionGroup as excgroup:
            messages = list[str]()
            for exc in flatten_exception_group(excgroup):
                if isinstance(exc, FetchError):
                    messages.append(exc.message)
                else:
                    messages.append(str(exc))
            return "\n".join(messages)

        args = dict[str, Any]()
        for option, result in arp.options.items():
            if result.value is None:
                args.update(result.args)
            else:
                args[option] = result.value

        if info.params.min_texts > 0 and len(texts) == 0:
            # 当所需文字数 > 0 且没有输入文字时，使用默认文字
            texts = info.params.default_texts

        if not (info.params.min_images <= len(images) <= info.params.max_images):
            return f"输入图片数量不符，图片数量应为 {info.params.min_images}" + (
                f" ~ {info.params.max_images}"
                if info.params.max_images > info.params.min_images
                else ""
            )
        if not (info.params.min_texts <= len(texts) <= info.params.max_texts):
            return f"输入文字数量不符，文字数量应为 {info.params.min_texts}" + (
                f" ~ {info.params.max_texts}"
                if info.params.max_texts > info.params.min_texts
                else ""
            )

        return await handle_meme_key(self.key, images, texts, args)


async def handle_meme_random(
    session: Session,
    meme_params: tuple[MemeParam, ...],
) -> str | MessageChain:
    texts, images = await handle_params(meme_params, session, 0)
    keys = [
        info.key
        for info in memes.values()
        if info.params.min_images <= len(images) <= info.params.max_images
        and info.params.min_texts <= len(texts) <= info.params.max_texts
    ]
    if not keys:
        return f"没有适用于 {len(images)} 张图片和 {len(texts)} 段文字的梗图"
    return await handle_meme_key(random.choice(keys), images, texts, {})
