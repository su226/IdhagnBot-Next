from collections.abc import Sequence
from typing import Any

from arclet import letoderea
from arclet.entari import (
    Element,
    MessageChain,
    MessageEvent,
    Session,
    Text,
    metadata,
    plugin_config,
)
from arclet.entari.config import EntariConfig
from arclet.entari.event.command import CommandReceive
from pydantic import BaseModel, Field


class Config(BaseModel):
    aliases: dict[str, dict[str, str]] = Field(default_factory=dict)
    default_prefix: str | None = None
    platform_default_prefix: dict[str, str] = Field(default_factory=dict)
    platform_disable_prefixes: dict[str, set[str]] = Field(default_factory=dict)


metadata("", config=Config)
CONFIG = plugin_config(Config)


def get_alias(session: Session[Any], name: str) -> str | None:
    if session.event.guild is None:
        guild = f"{session.account.platform}:private"
    else:
        guild = f"{session.account.platform}:{session.event.guild.id}"
    guild_aliases = CONFIG.aliases.get(guild)
    if guild_aliases is not None and name in guild_aliases:
        return guild_aliases[name]
    platform_aliases = CONFIG.aliases.get(session.account.platform)
    if platform_aliases is not None and name in platform_aliases:
        return platform_aliases[name]
    return None


def get_aliases(session: Session[Any]) -> dict[str, str]:
    if session.event.guild is None:
        guild = f"{session.account.platform}:private"
    else:
        guild = f"{session.account.platform}:{session.event.guild.id}"
    aliases = {}
    guild_aliases = CONFIG.aliases.get(guild)
    if guild_aliases is not None:
        aliases.update(guild_aliases)
    platform_aliases = CONFIG.aliases.get(session.account.platform)
    if platform_aliases is not None:
        aliases.update(platform_aliases)
    return aliases


def get_prefix(platform: str) -> str:
    if (prefix := CONFIG.platform_default_prefix.get(platform)) is not None:
        return prefix
    if CONFIG.default_prefix is not None:
        return CONFIG.default_prefix
    return EntariConfig.instance.basic.prefix[0]


def get_prefixes(platform: str) -> set[str]:
    disabled = CONFIG.platform_disable_prefixes.get(platform, set())
    return set(EntariConfig.instance.basic.prefix) - disabled


def has_command_prefix(
    platform: str,
    message: Sequence[Element],
) -> tuple[str, str] | None:
    prefixes = get_prefixes(platform)
    if not message or not isinstance(message[0], Text):
        return None
    splited = message[0].text.split(maxsplit=1)
    if not splited:
        return None
    first = splited[0]
    longest_prefix_len = 0
    for prefix in prefixes:
        if not prefix:
            continue
        if first.startswith(prefix) and len(prefix) > longest_prefix_len:
            longest_prefix_len = len(prefix)
    if longest_prefix_len > 0:
        return (first[:longest_prefix_len], first[longest_prefix_len:])
    return None


@letoderea.on(CommandReceive)
async def apply_rename_alias(
    session: Session[MessageEvent],
    content: MessageChain,
) -> None:
    original = session.event.content
    first = ""
    rest = ""
    if original and isinstance(original[0], Text):
        splited = original[0].text.split(maxsplit=1)
        if len(splited) == 2:
            first, rest = splited
        elif len(splited) == 1:
            first = splited[0]
    alias = get_alias(session, first)
    if alias is None:
        disable_prefixes = CONFIG.platform_disable_prefixes.get(
            session.account.platform,
        )
        if (
            disable_prefixes is not None
            and original
            and content
            and isinstance(original[0], Text)
            and isinstance(content[0], Text)
        ):
            prefix_len = original[0].text.index(content[0].text)
            prefix = original[0].text[:prefix_len]
            if prefix in disable_prefixes:
                content.clear()
        return
    if alias == "":
        content.clear()
    else:
        content[0] = Text(f"{alias} {rest}")
