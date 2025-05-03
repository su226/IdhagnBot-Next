import html
import math
from dataclasses import dataclass
from typing import Callable, Optional, Union

from pydantic import BaseModel, Field

from idhagnbot.config import SharedConfig
from idhagnbot.itertools import batched
from idhagnbot.permission import (
  ADMINISTRATOR_OR_ABOVE,
  OWNER_OR_ABOVE,
  SUPERUSER,
  Node,
  parse_node,
)
from idhagnbot.permission import check as check_permission


@dataclass
class ShowData:
  user_id: str
  current_group: str
  available_groups: list[str]
  private: bool
  sorted_roles: list[str]


def noop_condition(_: ShowData) -> bool:
  return True


class CommonData(BaseModel):
  priority: int = 0
  node: str = ""
  has_group: list[str] = Field(default_factory=list)
  in_group: list[str] = Field(default_factory=list)
  private: Optional[bool] = None
  default_grant_to: set[str] = Field(default_factory=lambda: {"default"})
  condition: Callable[["ShowData"], bool] = noop_condition

  @property
  def parsed_node(self) -> Node:
    return parse_node(self.node)

  @property
  def level(self) -> int:
    if self.default_grant_to == {"default"}:
      return 0
    if self.default_grant_to == ADMINISTRATOR_OR_ABOVE:
      return 1
    if self.default_grant_to == OWNER_OR_ABOVE:
      return 2
    if self.default_grant_to == SUPERUSER:
      return 3
    return 4

  @property
  def level_prefix(self) -> str:
    return {
      0: "",
      1: "[群管] ",
      2: "[群主] ",
      3: "[超管] ",
      4: "[其他] ",
    }[self.level]

  @property
  def level_prefix2(self) -> str:
    return {
      0: "",
      1: "群管 | ",
      2: "群主 | ",
      3: "超管 | ",
      4: "其他 | ",
    }[self.level]


class UserData(CommonData):
  category: str = ""


class UserString(UserData):
  string: str


class UserCommand(UserData):
  command: list[str]
  brief: str = ""
  usage: str = ""


class UserCategory(UserData):
  brief: str = ""


class Config(BaseModel):
  page_size: int = 10
  user_helps: list[Union[str, UserString, UserCommand, UserCategory]] = Field(default_factory=list)


CONFIG = SharedConfig("help", Config)
SEPARATOR = "══════════"


@CONFIG.onload()
def onload(prev: Optional[Config], curr: Config) -> None:
  if prev:
    CommandItem.remove_user_items()
    CategoryItem.ROOT.remove_user_items()
  for item in curr.user_helps:
    if isinstance(item, str):
      CategoryItem.ROOT.add(UserStringItem(item))
    elif isinstance(item, UserCategory):
      category = CategoryItem.find(item.category, True)
      if not isinstance(category, UserCategoryItem):
        continue
      category.brief = item.brief
      category.data = item
    elif isinstance(item, UserString):
      CategoryItem.find(item.category, True).add(UserStringItem(item.string, item))
    else:
      CategoryItem.find(item.category, True).add(
        UserCommandItem(item.command, item.brief, item.usage, item),
      )


class Item:
  def __init__(self, data: Optional[CommonData]) -> None:
    self.data = CommonData() if data is None else data

  def __call__(self) -> str:
    raise NotImplementedError

  def html(self) -> str:
    segments: list[str] = []
    if self.data.node:
      segments.append(f"权限节点: {self.data.node}")
    if self.data.has_group:
      segments.append(f"加入群聊: {'、'.join(str(x) for x in self.data.has_group)}")
    if self.data.in_group:
      groups = "、".join(str(x) for x in self.data.in_group)
      segments.append(f"在群聊中: {groups}")
    if self.data.private is not None:
      segments.append(f"私聊: {'仅私聊' if self.data.private else '仅群聊'}")
    if self.data.default_grant_to != {"default"}:
      segments.append(f"默认角色: {self.data.default_grant_to}")
    if segments:
      return "\n".join(segments)
    return ""

  def get_order(self) -> int:
    return 0

  def can_show(self, data: ShowData) -> bool:
    if not check_permission(self.data.parsed_node, data.sorted_roles, self.data.default_grant_to):
      return False
    # if self.data.in_group and not context.in_group(data.current_group, *self.data.in_group):
    #   return False
    if self.data.has_group and not any(i in self.data.has_group for i in data.available_groups):
      return False
    if self.data.private is not None and data.private != self.data.private:
      return False
    return self.data.condition(data)


class StringItem(Item):
  def __init__(self, string: str, data: Optional[CommonData] = None) -> None:
    super().__init__(data)
    self.string = string

  def __call__(self) -> str:
    return self.string

  def html(self) -> str:
    summary = html.escape(self.string)
    if (details := super().html()):
      return f"<details><summary>{summary}</summary>{details}</details>"
    return summary

  def get_order(self) -> int:
    return -1


class CommandItem(Item):
  commands: dict[str, "CommandItem"] = {}

  def __init__(
    self, names: Optional[list[str]] = None, brief: str = "",
    usage: Union[str, Callable[[], str]] = "", data: Optional[CommonData] = None,
  ) -> None:
    super().__init__(data)
    self.names = names or []
    self.raw_usage = usage
    self.brief = brief
    for i in self.names:
      if i in self.commands:
        raise ValueError(f"重复的命令名: {i}")
      self.commands[i] = self

  def html(self) -> str:
    if (info := super().html()):
      info = f"\n{info}"
    return (
      f'<details id="{html.escape(self.names[0])}"><summary>{html.escape(self())}</summary>'
      f"<pre>{html.escape(self.format(False))}{info}</pre></details>"
    )

  def get_order(self) -> int:
    return self.data.level

  @staticmethod
  def find(name: str) -> "CommandItem":
    return CommandItem.commands[name]

  def __call__(self) -> str:
    brief = f" - {self.brief}" if self.brief else ""
    return f"{self.data.level_prefix}/{self.names[0]}{brief}"

  def format(self, brief: bool = True) -> str:
    segments: list[str] = []
    if brief:
      segments.append(f"「{self.data.level_prefix2}{self.names[0]}」{self.brief}")
      segments.append(SEPARATOR)
    raw_usage = self.raw_usage
    if isinstance(raw_usage, Callable):
      raw_usage = raw_usage()
    raw_usage = raw_usage.replace("__cmd__", self.names[0])
    if len(raw_usage) == 0:
      segments.append("没有用法说明")
    else:
      segments.append(raw_usage)
    if len(self.names) > 1:
      segments.append(SEPARATOR)
      segments.append("该命令有以下别名：" + "、".join(self.names[1:]))
    return "\n".join(segments)

  @staticmethod
  def remove_user_items() -> None:
    remove_keys: list[str] = []
    for k, v in CommandItem.commands.items():
      if isinstance(v, UserCommandItem):
        remove_keys.append(k)
    for i in remove_keys:
      del CommandItem.commands[i]


class CategoryItem(Item):
  ROOT: "CategoryItem"

  def __init__(self, name: str, brief: str = "", data: Optional[CommonData] = None) -> None:
    super().__init__(data)
    self.name = name
    self.brief = brief
    self.items: list[Item] = []
    self.subcategories: dict[str, CategoryItem] = {}

  def __call__(self) -> str:
    brief = f" - {self.brief}" if self.brief else ""
    return f"📁{self.name}{brief}"

  def html(self, details: bool = True) -> str:
    content = "".join(f"<li>{x.html()}</li>" for x in sorted(
      self.items, key=lambda x: (-x.data.priority, x.get_order(), x())))
    if (info := super().html()):
      content = f"<pre>{info}</pre><ul>{content}</ul>"
    else:
      content = f"<ul>{content}</ul>"
    if details:
      return f"<details><summary>{html.escape(self())}</summary>{content}</details>"
    return f"{content}"

  def get_order(self) -> int:
    return -2

  @classmethod
  def find(
    cls, path: Union[str, list[str]], create: bool = False, check: Optional[ShowData] = None,
  ) -> "CategoryItem":
    cur = CategoryItem.ROOT
    if isinstance(path, str):
      path = [x for x in path.split(".") if x]
    for i, name in enumerate(path, 1):
      if name not in cur.subcategories:
        if not create:
          raise KeyError(f"子分类 {'.'.join(path[:i])} 不存在")
        sub = cls(name)
        cur.add(sub)
        cur = sub
      else:
        cur = cur.subcategories[name]
        if check and not cur.can_show(check):
          raise ValueError(f"子分类 {'.'.join(path[:i])} 不能显示")
    return cur

  def add(self, item: Item) -> None:
    if isinstance(item, CategoryItem):
      if item.name in self.subcategories:
        raise ValueError(f"重复的子分类名: {item.name}")
      self.subcategories[item.name] = item
    self.items.append(item)

  def format_page(self, show_data: ShowData, path: list[str], page: int) -> tuple[str, int]:
    config = CONFIG()
    vaild_items = sorted(
      ((x(), x) for x in self.items if x.can_show(show_data)),
      key=lambda x: (-x[1].data.priority, x[1].get_order(), x[0]),
    )
    total_pages = math.ceil(len(vaild_items) / config.page_size)
    vaild_items = vaild_items[config.page_size * page:config.page_size * (page + 1)]
    has_command = False
    has_category = False
    lines: list[str] = []
    for formatted, item in vaild_items:
      if isinstance(item, CommandItem):
        has_command = True
      elif isinstance(item, CategoryItem):
        has_category = True
      lines.append(formatted)
    lines.append(SEPARATOR)
    lines.append(f"第 {page + 1} 页，共 {total_pages} 页")
    header_lines: list[str] = []
    if has_command:
      header_lines.append(
        "ℹ 斜线「/」开头的是命令，发送「/help <命令名>」查看，"
        "比如假设有「/某个命令」，就需要发送「/help 某个命令」来查看",
      )
    if has_category:
      path_str = "".join(f" {i}" for i in path)
      header_lines.append(
        f"ℹ 文件夹「📁」开头的是分类，发送「/help {path_str}<分类名>」查看，"
        f"比如假设有「📁某个分类」，就需要发送「/help {path_str}某个分类」来查看",
      )
    if header_lines:
      lines = [*header_lines, SEPARATOR, *lines]
    return "\n".join(lines), total_pages


  def format_all(self, show_data: ShowData, path: list[str]) -> list[str]:
    config = CONFIG()
    vaild_items = sorted(
      ((x(), x) for x in self.items if x.can_show(show_data)),
      key=lambda x: (-x[1].data.priority, x[1].get_order(), x[0]),
    )
    has_command = False
    has_category = False
    nodes: list[str] = []
    for chunk in batched(vaild_items, config.page_size):
      lines: list[str] = []
      for formatted, item in chunk:
        if isinstance(item, CommandItem):
          has_command = True
        elif isinstance(item, CategoryItem):
          has_category = True
        lines.append(formatted)
      nodes.append("\n".join(lines))
    header_lines: list[str] = []
    if has_command:
      header_lines.append(
        "ℹ 斜线「/」开头的是命令，发送「/help <命令名>」查看，"
        "比如假设有「/某个命令」，就需要发送「/help 某个命令」来查看",
      )
    if has_category:
      path_str = "".join(f" {i}" for i in path)
      header_lines.append(
        f"ℹ 文件夹「📁」开头的是分类，发送「/help {path_str}<分类名>」查看，"
        f"比如假设有「📁某个分类」，就需要发送「/help {path_str}某个分类」来查看",
      )
    if header_lines:
      return ["\n".join(header_lines), *nodes]
    return nodes

  def remove_user_items(self) -> None:
    self.items = [item for item in self.items if not isinstance(item, UserItem)]
    remove_keys: list[str] = []
    for k, v in self.subcategories.items():
      if isinstance(v, UserCategoryItem):
        remove_keys.append(k)
      else:
        v.remove_user_items()
    for k in remove_keys:
      del self.subcategories[k]


CategoryItem.ROOT = CategoryItem("root")


class UserItem(Item):
  pass


class UserStringItem(StringItem, UserItem):
  pass


class UserCommandItem(CommandItem, UserItem):
  pass


class UserCategoryItem(CategoryItem, UserItem):
  pass


def export_index_html() -> str:
  segments = (
    f'<li><a href="#{html.escape(command.names[0])}">'
    f"{command.data.level_prefix}{html.escape(name)}</a></li>"
    for name, command in sorted(CommandItem.commands.items(), key=lambda x: x[0])
  )
  return f"<ul>{''.join(segments)}</ul>"
