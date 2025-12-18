from typing import Any

import nonebot
from arclet.alconna import config
from nonebot.typing import T_State
from typing_extensions import Self

from idhagnbot.help import CategoryItem, CommandItem, CommonData
from idhagnbot.permission import DEFAULT, permission

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Alconna, AlconnaMatcher, Extension, on_alconna

config.command_max_count = 1000


class CommandBuilder:
  _node: str
  _category: str
  _default_grant_to: set[str]
  _parser: Alconna[Any] | None
  _aliases: set[str]
  _state: dict[str, Any] | None
  _auto_reject: bool
  _extensions: list[type[Extension] | Extension]

  def __init__(self) -> None:
    super().__init__()
    self._node = ""
    self._category = ""
    self._default_grant_to = DEFAULT
    self._parser = None
    self._aliases = set()
    self._state = None
    self._auto_reject = True
    self._extensions = []

  def node(self, node: str) -> Self:
    self._node = node
    return self

  def category(self, category: str) -> Self:
    self._category = category
    return self

  def default_grant_to(self, roles: set[str]) -> Self:
    self._default_grant_to = roles
    return self

  def parser(self, parser: Alconna[Any]) -> Self:
    self._parser = parser
    return self

  def aliases(self, aliases: set[str]) -> Self:
    self._aliases = aliases
    return self

  def state(self, state: T_State) -> Self:
    self._state = state
    return self

  def auto_reject(self, auto_reject: bool) -> Self:
    self._auto_reject = auto_reject
    return self

  def extension(self, *extensions: type[Extension] | Extension) -> Self:
    self._extensions.extend(extensions)
    return self

  def build(self) -> type[AlconnaMatcher]:
    if not self._node:
      raise ValueError("node is required")
    if not self._parser:
      raise ValueError("parser is required")
    parser = self._parser
    CategoryItem.find(self._category, create=True).add(
      CommandItem(
        [parser.name, *self._aliases],
        parser.meta.description,
        lambda: parser.formatter.format_node(),
        CommonData(
          node=self._node,
          default_grant_to=self._default_grant_to,
        ),
      ),
    )
    return on_alconna(
      parser,
      aliases=self._aliases,
      extensions=self._extensions,
      permission=permission(self._node, self._default_grant_to),
      default_state=self._state,
      auto_send_output=self._auto_reject,
      skip_for_unmatch=not self._auto_reject,
      use_cmd_start=True,
      _depth=1,
    )
