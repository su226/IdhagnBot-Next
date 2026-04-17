from typing import Any, Self, cast

import nonebot
from arclet.alconna import config
from nonebot.exception import FinishedException
from nonebot.message import event_preprocessor
from nonebot.typing import T_State

from idhagnbot.help import CategoryItem, CommandItem, CommandName, CommonData
from idhagnbot.message import UniMsg
from idhagnbot.permission import DEFAULT, permission

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import (
  Alconna,
  AlconnaMatcher,
  CommandResult,
  Extension,
  Text,
  UniMessage,
  command_manager,
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
  __aliases: dict[str, str | None]
  __state: dict[str, Any] | None
  __auto_reject: bool
  __extensions: list[type[Extension] | Extension]

  def __init__(self) -> None:
    super().__init__()
    self.__node = ""
    self.__category = ""
    self.__default_grant_to = DEFAULT
    self.__parser = None
    self.__aliases = {}
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

  def aliases(self, aliases: set[str] | dict[str, str | None]) -> Self:
    self.__aliases = dict.fromkeys(aliases) if isinstance(aliases, set) else aliases
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
    names = [CommandName(parser.name, None)]
    names.extend(CommandName(name, locale) for name, locale in self.__aliases.items())
    item = CommandItem(
      names,
      parser.meta.description,
      cast(Any, parser.formatter.format_node),
      CommonData(
        node=self.__node,
        default_grant_to=self.__default_grant_to,
      ),
    )
    CategoryItem.find(self.__category, create=True).add(item)
    matcher = on_alconna(
      parser,
      aliases=set(self.__aliases),
      extensions=self.__extensions,
      permission=permission(self.__node, self.__default_grant_to),
      default_state=self.__state,
      skip_for_unmatch=not self.__auto_reject,
      auto_send_output=False,
      use_cmd_start=True,
      _depth=1,
    )

    def destroy() -> None:
      item.remove_self()
      matcher.clean()

    matcher.destroy = destroy
    if self.__auto_reject:
      matcher.handle()(send_output)
    return matcher


COMMAND_KEY = "_idhagnbot_command"
COMMAND_LIKE_KEY = "_idhagnbot_command_like"
DRIVER = nonebot.get_driver()


@event_preprocessor
async def _(message: UniMsg, state: T_State) -> None:
  if command_manager.test(message):
    state[COMMAND_KEY] = True
  segment = message[0]
  if isinstance(segment, Text):
    longest_prefix_len = 0
    first = segment.text.split(None, 1)[0]
    for prefix in DRIVER.config.command_start:
      if prefix and first.startswith(prefix):
        longest_prefix_len = max(longest_prefix_len, len(prefix))
    if longest_prefix_len:
      state[COMMAND_LIKE_KEY] = (first[:longest_prefix_len], first[longest_prefix_len:])
