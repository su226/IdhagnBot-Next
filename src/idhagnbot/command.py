from typing import Any, Self, cast

import nonebot
from arclet.alconna import config
from nonebot.exception import FinishedException
from nonebot.typing import T_State

from idhagnbot.help import CategoryItem, CommandItem, CommonData
from idhagnbot.permission import DEFAULT, permission

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import (
  Alconna,
  AlconnaMatcher,
  CommandResult,
  Extension,
  UniMessage,
  on_alconna,
)

config.command_max_count = 1000


async def send_output(result: CommandResult) -> None:
  if result.output is not None:
    await UniMessage(result.output).send()
    raise FinishedException


class CommandBuilder:
  __node: str
  __category: str
  __default_grant_to: set[str]
  __parser: Alconna[Any] | None
  __aliases: set[str]
  __state: dict[str, Any] | None
  __auto_reject: bool
  __extensions: list[type[Extension] | Extension]

  def __init__(self) -> None:
    super().__init__()
    self.__node = ""
    self.__category = ""
    self.__default_grant_to = DEFAULT
    self.__parser = None
    self.__aliases = set()
    self.__state = None
    self.__auto_reject = True
    self.__extensions = []

  def node(self, node: str) -> Self:
    self.__node = node
    return self

  def category(self, category: str) -> Self:
    self.__category = category
    return self

  def default_grant_to(self, roles: set[str]) -> Self:
    self.__default_grant_to = roles
    return self

  def parser(self, parser: Alconna[Any]) -> Self:
    self.__parser = parser
    return self

  def aliases(self, aliases: set[str]) -> Self:
    self.__aliases = aliases
    return self

  def state(self, state: T_State) -> Self:
    self.__state = state
    return self

  def auto_reject(self, auto_reject: bool) -> Self:
    self.__auto_reject = auto_reject
    return self

  def extension(self, *extensions: type[Extension] | Extension) -> Self:
    self.__extensions.extend(extensions)
    return self

  def build(self) -> type[AlconnaMatcher]:
    if not self.__node:
      raise ValueError("node is required")
    if not self.__parser:
      raise ValueError("parser is required")
    parser = self.__parser
    CategoryItem.find(self.__category, create=True).add(
      CommandItem(
        [parser.name, *self.__aliases],
        parser.meta.description,
        cast(Any, parser.formatter.format_node),
        CommonData(
          node=self.__node,
          default_grant_to=self.__default_grant_to,
        ),
      ),
    )
    matcher = on_alconna(
      parser,
      aliases=self.__aliases,
      extensions=self.__extensions,
      permission=permission(self.__node, self.__default_grant_to),
      default_state=self.__state,
      skip_for_unmatch=not self.__auto_reject,
      auto_send_output=False,
      use_cmd_start=True,
      _depth=1,
    )
    if self.__auto_reject:
      matcher.handle()(send_output)
    return matcher
