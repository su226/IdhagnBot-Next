import asyncio
import json
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiohttp import ClientError, FormData
from arclet.alconna import (
    Alconna,
    ArgFlag,
    Args,
    Arparma,
    CommandMeta,
    Empty,
    MultiVar,
    Option,
)
from arclet.alconna.action import Action
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

from idhagnbot.http import get_session
from idhagnbot.meme_common import (
    FetchError,
    MemeImage,
    MemeParam,
    flatten_exception_group,
    handle_params,
)


class Config(BaseModel):
    base_url: HttpUrl | None = None


class ParserArg(BaseModel):
    name: str
    value: str
    default: Any | None = None
    flags: list[ArgFlag] | None = None


class ParserOption(BaseModel):
    names: list[str]
    args: list[ParserArg] | None = None
    dest: str | None = None
    default: Any | None = None
    action: Action | None = None
    help_text: str | None = None
    compact: bool = False

    def option(self) -> Option:
        args = Args()
        for arg in self.args or []:
            args.add(
                name=arg.name,
                value=arg.value,
                default=arg.default or Empty,
                flags=arg.flags,
            )

        return Option(
            name="|".join(self.names),
            args=args,
            dest=self.dest,
            default=self.default or Empty,
            action=self.action,
            help_text=self.help_text,
            compact=self.compact,
        )


class CommandShortcut(BaseModel):
    key: str
    args: list[str] | None = None
    humanized: str | None = None


class MemeArgsType(BaseModel):
    args_model: dict[str, Any]
    args_examples: list[dict[str, Any]]
    parser_options: list[ParserOption]


class MemeParamsType(BaseModel):
    min_images: int
    max_images: int
    min_texts: int
    max_texts: int
    default_texts: list[str]
    args_type: MemeArgsType | None = None


class MemeInfo(BaseModel):
    key: str
    params_type: MemeParamsType
    keywords: list[str]
    shortcuts: list[CommandShortcut]
    tags: set[str]
    date_created: datetime
    date_modified: datetime


metadata("", config=Config)
CONFIG = plugin_config(Config)
memes = dict[str, MemeInfo]()


async def add_matcher(key: str) -> None:
    http = get_session()
    async with http.get(
        f"{CONFIG.base_url}memes/{key}/info",
        raise_for_status=True,
    ) as response:
        info = MemeInfo.model_validate_json(await response.text())
    memes[key] = info
    options = (
        info.params_type.args_type.parser_options if info.params_type.args_type else []
    )
    cmd = Alconna(
        info.keywords[0],
        *(opt.option() for opt in options),
        Args["meme_params", MultiVar(MemeParam, "*")],
        namespace="memes",
    )
    for keyword in info.keywords[1:]:
        cmd.shortcut(keyword, command=info.keywords[0])
    command.on(cmd)(MemeHandler(info.key).handle).propagate(
        require_permission(f"idhagnbot.meme_generator.{info.key}", prompt=True),
    )


@on(Ready)
async def add_matchers() -> None:
    if not CONFIG.base_url:
        return
    http = get_session()
    while True:
        try:
            async with http.get(
                f"{CONFIG.base_url}memes/keys",
                raise_for_status=True,
            ) as response:
                keys = TypeAdapter(list[str]).validate_json(await response.text())
                break
        except ClientError:
            logger.exception("初始化 meme_generator 失败")
            await asyncio.sleep(10)
    async with asyncio.TaskGroup() as tg:
        for key in keys:
            tg.create_task(add_matcher(key))
    command.on(
        Alconna(
            "随机梗图",
            Args["meme_params", MultiVar(MemeParam, "*")],
            meta=CommandMeta("制作符合参数数量的随机梗图"),
        ),
    )(handle_meme_random).propagate(
        require_permission("idhagnbot.meme_generator.random", prompt=True),
    )


async def handle_meme_key(
    key: str,
    images: list[MemeImage],
    texts: list[str],
    args: dict[str, Any],
) -> str | MessageChain:
    form = FormData()
    for image in images:
        form.add_field("images", image.image, filename="image")
    for text in texts:
        form.add_field("texts", text)
    form.add_field("args", json.dumps(args))
    async with get_session().post(
        f"{CONFIG.base_url}memes/{key}/",
        data=form,
    ) as response:
        if response.status != 200:
            error = await response.json()
            return error["detail"]
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
                info.params_type.min_images,
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

        users = list[dict[str, str]]()
        for image in images:
            if image.name:
                users.append({"name": image.name, "gender": image.gender})
        args["user_infos"] = users

        if info.params_type.min_texts > 0 and len(texts) == 0:
            # 当所需文字数 > 0 且没有输入文字时，使用默认文字
            texts = info.params_type.default_texts

        if not (
            info.params_type.min_images <= len(images) <= info.params_type.max_images
        ):
            return f"输入图片数量不符，图片数量应为 {info.params_type.min_images}" + (
                f" ~ {info.params_type.max_images}"
                if info.params_type.max_images > info.params_type.min_images
                else ""
            )
        if not (info.params_type.min_texts <= len(texts) <= info.params_type.max_texts):
            return f"输入文字数量不符，文字数量应为 {info.params_type.min_texts}" + (
                f" ~ {info.params_type.max_texts}"
                if info.params_type.max_texts > info.params_type.min_texts
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
        if info.params_type.min_images <= len(images) <= info.params_type.max_images
        and info.params_type.min_texts <= len(texts) <= info.params_type.max_texts
    ]
    if not keys:
        return f"没有适用于 {len(images)} 张图片和 {len(texts)} 段文字的梗图"
    return await handle_meme_key(random.choice(keys), images, texts, {})
