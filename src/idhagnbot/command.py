from typing import Any

import nonebot
from nonebot.typing import T_State
from typing_extensions import Self

from idhagnbot.help import CategoryItem, CommandItem, CommonData
from idhagnbot.permission import DEFAULT, permission

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Alconna, AlconnaMatcher, on_alconna


class CommandBuilder:
  def __init__(self) -> None:
    self._node = ""
    self._category = ""
    self._default_grant_to = DEFAULT
    self._parser: Alconna[Any] | None = None
    self._aliases: set[str] = set()
    self._state = None
    self._auto_reject = True

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

  def build(self) -> type[AlconnaMatcher]:
    if not self._node:
      raise ValueError("node is required")
    if not self._parser:
      raise ValueError("parser is required")
    CategoryItem.find(self._category, True).add(
      CommandItem(
        [self._parser.name, *self._aliases],
        self._parser.meta.description,
        self._parser.formatter.format_node,
        CommonData(
          node=self._node,
          default_grant_to=self._default_grant_to,
        ),
      ),
    )
    return on_alconna(
      self._parser,
      aliases=self._aliases,
      permission=permission(self._node, self._default_grant_to),
      default_state=self._state,
      auto_send_output=self._auto_reject,
      skip_for_unmatch=not self._auto_reject,
      use_cmd_start=True,
      _depth=1,
    )
