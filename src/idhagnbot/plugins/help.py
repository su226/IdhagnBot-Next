import math
from collections.abc import Callable
from dataclasses import dataclass
from itertools import batched
from typing import no_type_check
from uuid import uuid4

from arclet import letoderea
from arclet.alconna import Alconna, Args, CommandMeta, command_manager
from arclet.entari import (
    Button,
    Message,
    MessageChain,
    Session,
    Text,
    command,
    enter_if,
    metadata,
    plugin_config,
)
from arclet.entari.command import Match
from entari_plugin_permission import require_permission  # entari: plugin
from pydantic import BaseModel, Field
from tarina import lang

from idhagnbot.i18n import bound_lang, get_locales
from idhagnbot.plugins.alias import get_prefix
from idhagnbot.plugins.button import ManagedButtonEvent, register_button
from idhagnbot.support import support_batch_forward, support_button


class Config(BaseModel):
    default_page_size: int = 10
    platform_page_size: dict[str, int] = Field(default_factory=dict)


metadata("", config=Config)
CONFIG = plugin_config(Config)
L = bound_lang("idhagnbot_help")


def get_preferred_name(cmd: Alconna, locales: dict[str, int]) -> str:
    names = cmd.meta.extra.get("idhagnbot_i18n_names")
    if names is not None:
        best_name = cmd.name
        best_preference = 999
        for name, locale in names.items():
            preference = locales.get(locale)
            if preference is not None and preference < best_preference:
                best_name = name
                best_preference = preference
        return best_name
    return cmd.name


@dataclass
class CommandWithName:
    command: Alconna
    name: str


locale_matcher = None


@no_type_check  # pyicu missing stubs will result unresolved-attribute
def get_icu_collator(locales: dict[str, int]) -> Callable[[str], bytes]:
    import icu

    global locale_matcher
    if locale_matcher is None:
        locale_matcher = (
            icu.LocaleMatcher.Builder()
            .setSupportedLocales(list(icu.Collator.getAvailableLocales().values()))
            .build()
        )
    preferences = sorted(locales.keys(), key=lambda x: locales[x])
    preferences = [icu.Locale(locale) for locale in preferences]
    preferences.append(icu.Locale.getDefault())
    locale = locale_matcher.getBestMatch(preferences)
    collator = icu.Collator.createInstance(locale)
    collator.setAttribute(
        icu.UCollAttribute.NUMERIC_COLLATION,
        icu.UCollAttributeValue.ON,
    )
    return collator.getSortKey


def get_collator(
    locales: dict[str, int],
) -> Callable[[str], str] | Callable[[str], bytes]:
    try:
        return get_icu_collator(locales)
    except ImportError:
        return lambda x: x


def get_sorted_commands(
    namespace: str,
    locales: dict[str, int],
) -> list[CommandWithName]:
    collator = get_collator(locales)
    return sorted(
        (
            CommandWithName(cmd, get_preferred_name(cmd, locales))
            for cmd in command_manager.get_commands(namespace)
            if not cmd.meta.hide
        ),
        key=lambda cmd: collator(cmd.name),
    )


def format_command(prefix: str, cmd: CommandWithName) -> str:
    if (key := cmd.command.meta.extra.get("idhagnbot_i18n_description")) is not None:
        namespace, key = key.split(":", maxsplit=1)
        description = lang.require(namespace, key)
    elif cmd.command.meta.description == "Unknown":
        description = None
    else:
        description = cmd.command.meta.description
    if description is None:
        return f"{prefix}{cmd.name}"
    return f"{prefix}{cmd.name} {description}"


def format_page(
    platform: str,
    namespace: str,
    page: int,
    page_size: int,
) -> tuple[str, int, int]:
    locales = {locale: preference for preference, locale in enumerate(get_locales())}
    commands = get_sorted_commands(namespace, locales)
    total_page = math.ceil(len(commands) / page_size)
    actual_page = min(max(page, 1), total_page)
    page_start = (actual_page - 1) * page_size
    page_end = actual_page * page_size
    prefix = get_prefix(platform)
    lines = [format_command(prefix, cmd) for cmd in commands[page_start:page_end]]
    lines.append(L("paginator").format(page=actual_page, total=total_page))
    return "\n".join(lines), actual_page, total_page


def format_pages(platform: str, namespace: str, page_size: int) -> list[str]:
    locales = {locale: preference for preference, locale in enumerate(get_locales())}
    prefix = get_prefix(platform)
    return [
        "\n".join(format_command(prefix, cmd) for cmd in page)
        for page in batched(
            get_sorted_commands(namespace, locales),
            page_size,
            strict=False,
        )
    ]


def get_page_size(platform: str) -> int:
    if (page_size := CONFIG.platform_page_size.get(platform)) is not None:
        return page_size
    return CONFIG.default_page_size


async def check_button(event: ManagedButtonEvent) -> bool:
    return event.type == "help"


@letoderea.on(ManagedButtonEvent)
@enter_if(check_button)
async def handle_button(event: ManagedButtonEvent) -> None:
    namespace = event.data["namespace"]
    page = event.data["page"]
    content, actual_page, total_page = format_page(
        event.origin.account.platform,
        namespace,
        page,
        get_page_size(event.origin.account.platform),
    )
    message = MessageChain([Text(content)])
    if actual_page > 1:
        prev_id = uuid4()
        button = Button.action(str(prev_id))
        button.children.append(Text("<"))
        message.append(button)
        await register_button(
            prev_id,
            event.channel.id,
            event.user.id,
            event.message.id,
            "help",
            {"namespace": namespace, "page": actual_page - 1},
        )
    if actual_page < total_page:
        next_id = uuid4()
        button = Button.action(str(next_id))
        button.children.append(Text(">"))
        message.append(button)
        await register_button(
            next_id,
            event.channel.id,
            event.user.id,
            event.message.id,
            "help",
            {"namespace": namespace, "page": actual_page + 1},
        )
    await event.origin.account.message_update(
        event.channel.id,
        event.message.id,
        str(message),
    )


help_alc = Alconna(
    "help",
    Args["namespace?", str, "Alconna"],
    Args["page?", int, 1],
    meta=CommandMeta(
        description="查看所有帮助。",
        extra={
            "idhagnbot_i18n_description": "idhagnbot_help:command_brief_help",
            "idhagnbot_i18n_names": {
                "help": "en-US",
                "帮助": "zh-CN",
            },
        },
    ),
)
help_alc.shortcut("帮助", command="help")
help_cmd = command.mount(help_alc, skip_for_unmatch=False)
help_cmd.propagators.append(require_permission("idhagnbot.help", prompt=True))
help_exe = help_cmd.for_execute()


@help_cmd.handle()
async def handle_help(
    session: Session,
    namespace: Match[str],
    page: Match[int],
) -> None:
    page_size = get_page_size(session.account.platform)
    if support_batch_forward(session.account.platform):
        pages = format_pages(
            session.account.platform,
            namespace.result,
            page_size,
        )
        message = Message(
            forward=True,
            content=[Message(content=[Text(page)]) for page in pages],
        )
        await session.send([message])
        return
    content, actual_page, total_page = format_page(
        session.account.platform,
        namespace.result,
        page.result,
        page_size,
    )
    message = MessageChain(Text(content))
    prev_id = None
    next_id = None
    if support_button(session.account.platform):
        if actual_page > 1:
            prev_id = uuid4()
            button = Button.action(str(prev_id))
            button.children.append(Text("<"))
            message.append(button)
        if actual_page < total_page:
            next_id = uuid4()
            button = Button.action(str(next_id))
            button.children.append(Text(">"))
            message.append(button)
    receipts = await session.send(message)
    receipt = receipts[0]
    if prev_id is not None:
        await register_button(
            prev_id,
            session.channel.id,
            session.user.id,
            receipt.id,
            "help",
            {"namespace": namespace.result, "page": actual_page - 1},
        )
    if next_id is not None:
        await register_button(
            next_id,
            session.channel.id,
            session.user.id,
            receipt.id,
            "help",
            {"namespace": namespace.result, "page": actual_page + 1},
        )


@help_exe.handle()
async def execute_help(
    session: Session,
    namespace: Match[str],
    page: Match[int],
) -> str:
    content, _, _ = format_page(
        session.account.platform,
        namespace.result,
        page.result,
        get_page_size(session.account.platform),
    )
    return content
