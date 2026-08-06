import asyncio
from typing import override

from arclet.entari import Message, MessageChain, Text
from loguru import logger
from pydantic import Field
from satori.element import Br

from idhagnbot.asyncio import create_background_task, gather_map
from idhagnbot.plugins.daily_push.module import (
    ComplexModule,
    Module,
    ModuleConfig,
    SimpleModule,
    Target,
    TargetAwareModule,
)
from idhagnbot.plugins.error_report import send_error


async def format_simple(
    module: SimpleModule,
    targets: list[Target],
) -> dict[Target, list[MessageChain]]:
    try:
        content = await module.format()
    except BaseException as e:
        logger.exception(f"每日推送模块运行失败: type={module.type!r} {module}")
        description = f"模块运行失败：{module.type}"
        create_background_task(send_error("daily_push", description, e))
        content = [MessageChain(Text(description))]
    return dict.fromkeys(targets, content)


async def format_one_target_aware(
    module: TargetAwareModule,
    target: Target,
) -> list[MessageChain]:
    try:
        return await module.format(target)
    except BaseException as e:
        logger.exception(f"每日推送模块运行失败: type={module.type!r} {module}")
        description = f"模块运行失败：{module.type}"
        create_background_task(send_error("daily_push", description, e))
        return [MessageChain(Text(description))]


async def format_target_aware(
    module: TargetAwareModule,
    targets: list[Target],
) -> dict[Target, list[MessageChain]]:
    return await gather_map(
        {target: format_one_target_aware(module, target) for target in targets},
    )


async def format_complex(
    module: ComplexModule,
    targets: list[Target],
) -> dict[Target, list[MessageChain]]:
    try:
        return await module.format(targets)
    except BaseException as e:
        logger.exception(f"每日推送模块运行失败: type={module.type!r} {module}")
        description = f"模块运行失败：{module.type}"
        create_background_task(send_error("daily_push", description, e))
        content = [MessageChain(Text(description))]
        return dict.fromkeys(targets, content)


def to_modules(configs: ModuleConfig | list[ModuleConfig]) -> list[Module]:
    if not isinstance(configs, list):
        return [configs.to_module()]
    return [module.to_module() for module in configs]


async def format_modules(
    targets: list[Target],
    configs: ModuleConfig | list[ModuleConfig],
) -> dict[Target, list[MessageChain]]:
    if not targets:
        return {}
    modules = to_modules(configs)
    tasks = []
    async with asyncio.TaskGroup() as tg:
        for module in modules:
            if isinstance(module, SimpleModule):
                tasks.append(tg.create_task(format_simple(module, targets)))
            elif isinstance(module, TargetAwareModule):
                tasks.append(tg.create_task(format_target_aware(module, targets)))
            else:
                tasks.append(tg.create_task(format_complex(module, targets)))
    results = {target: [] for target in targets}
    for task in tasks:
        for target, contents in task.result().items():
            results[target].extend(contents)
    return results


def merge_messages(messages: list[MessageChain]) -> MessageChain:
    result = MessageChain()
    for i, message in enumerate(messages):
        if i > 0:
            result += Br()
        result += message
    return result


def forward_messages(messages: list[MessageChain]) -> Message:
    return Message(
        forward=True,
        content=[Message(content=message) for message in messages],
    )


class GroupModule(ComplexModule):
    type = "group"
    content: ModuleConfig | list[ModuleConfig]
    header: ModuleConfig | list[ModuleConfig] = Field(default_factory=list)
    separator: ModuleConfig | list[ModuleConfig] = Field(default_factory=list)
    footer: ModuleConfig | list[ModuleConfig] = Field(default_factory=list)
    merge: bool = False
    forward: bool = False

    @override
    async def format(self, targets: list[Target]) -> dict[Target, list[MessageChain]]:
        content = await format_modules(targets, self.content)
        need_affix = []
        need_separator = []
        for target, messages in content.items():
            if len(messages) > 1:
                need_separator.append(target)
            if messages:
                need_affix.append(target)
        header, separator, footer = await asyncio.gather(
            format_modules(need_affix, self.header),
            format_modules(need_separator, self.separator),
            format_modules(need_affix, self.footer),
        )
        result = {target: [] for target in targets}
        for target, messages in content.items():
            if not messages:
                continue
            out_messages = result[target]
            out_messages.extend(header[target])
            for i, content_msg in enumerate(messages):
                if i > 0:
                    out_messages.extend(separator[target])
                out_messages.append(content_msg)
            out_messages.extend(footer[target])
        if self.merge:
            result = {
                target: [merge_messages(messages)]
                for target, messages in result.items()
            }
        if self.forward:
            result = {
                target: [MessageChain(forward_messages(messages))]
                for target, messages in result.items()
            }
        return result
