import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

import nonebot
from pydantic import BaseModel, Field
from pypinyin import lazy_pinyin
from typing_extensions import override

from idhagnbot.config import SharedConfig
from idhagnbot.context import in_scene
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
class Context:
  scope: str
  user_id: str
  current_scene: str
  available_scenes: set[str]
  private: bool
  roles: set[str]


def noop_condition(_: Context) -> bool:
  return True


class CommonData(BaseModel):
  priority: int = 0
  node: str = ""
  scope: str = ""
  has_scene: set[str] = Field(default_factory=set)
  in_scene: set[str] = Field(default_factory=set)
  private: bool | None = None
  default_grant_to: set[str] = Field(default_factory=lambda: {"default"})
  condition: Callable[["Context"], bool] = noop_condition

  @property
  def parsed_node(self) -> Node:
    return parse_node(self.node)

  @property
  def order(self) -> int:
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
  def prefix(self) -> str:
    return {
      0: "",
      1: "群管",
      2: "群主",
      3: "超管",
      4: "其他",
    }[self.order]

  def format_prefix(self, fmt: str) -> str:
    prefix = self.prefix
    return fmt.format(prefix) if prefix else ""


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
  user_helps: list[str | UserString | UserCommand | UserCategory] = Field(default_factory=list)


CONFIG = SharedConfig("help", Config)
SEPARATOR = "══════════"
COMMAND_PREFIX = next(iter(nonebot.get_driver().config.command_start))


@CONFIG.onload()
def onload(prev: Config | None, curr: Config) -> None:
  if prev:
    CategoryItem.ROOT.remove_user_items()
  for item in curr.user_helps:
    if isinstance(item, str):
      CategoryItem.ROOT.add(UserStringItem(item))
    elif isinstance(item, UserCategory):
      category = UserCategoryItem.find(item.category, create=True)
      if not isinstance(category, UserCategoryItem):
        continue
      category.brief = item.brief
      category.data = item
    elif isinstance(item, UserString):
      category = UserCategoryItem.find(item.category, create=True)
      category.add(UserStringItem(item.string, item))
    else:
      category = UserCategoryItem.find(item.category, create=True)
      category.add(UserCommandItem(item.command, item.brief, item.usage, item))


class Item:
  data: CommonData
  parent: "CategoryItem | None"

  def __init__(self, data: CommonData | None = None) -> None:
    self.data = data or CommonData()
    self.parent = None

  def remove_self(self) -> None:
    if not self.parent:
      raise ValueError("帮助项不在任何一个分类中")
    self.parent.remove(self)

  def check(self, ctx: Context) -> bool:
    if not check_permission(self.data.parsed_node, ctx.roles, self.data.default_grant_to):
      return False
    if self.data.scope and ctx.scope != self.data.scope:
      return False
    if self.data.in_scene and not in_scene(ctx.current_scene, self.data.in_scene):
      return False
    if self.data.has_scene and not any(i in self.data.has_scene for i in ctx.available_scenes):
      return False
    if self.data.private is not None and ctx.private != self.data.private:
      return False
    return self.data.condition(ctx)

  @property
  def order(self) -> int:
    return 0

  def get_sort_key(self) -> list[str]:
    raise NotImplementedError

  def format_title(self) -> str:
    raise NotImplementedError


def get_sort_key(title: str) -> list[str]:
  # 将没有拼音的字符转为大写，拼音保持小写，确保英文指令在中文指令前面
  return lazy_pinyin(title, errors=str.upper)


class StringItem(Item):
  string: str

  def __init__(self, title: str, data: CommonData | None = None) -> None:
    super().__init__(data)
    self.string = title

  @property
  @override
  def order(self) -> int:
    return -1

  @override
  def get_sort_key(self) -> list[str]:
    return get_sort_key(self.string)

  @override
  def format_title(self) -> str:
    return self.string


class CommandItem(Item):
  COMMANDS: ClassVar[dict[str, "CommandItem"]] = {}

  names: list[str]
  brief: str
  usage: str | Callable[[], str]

  def __init__(
    self,
    names: list[str],
    brief: str = "",
    usage: str | Callable[[], str] = "",
    data: CommonData | None = None,
  ) -> None:
    super().__init__(data)
    self.names = names
    self.usage = usage
    self.brief = brief
    for i in names:
      if i in self.COMMANDS:
        raise ValueError(f"重复的命令名: {i}")
      self.COMMANDS[i] = self

  @override
  def remove_self(self) -> None:
    super().remove_self()
    for name in self.names:
      del self.COMMANDS[name]

  @property
  @override
  def order(self) -> int:
    return self.data.order

  @override
  def get_sort_key(self) -> list[str]:
    return get_sort_key(self.names[0])

  @override
  def format_title(self) -> str:
    brief = f" - {self.brief}" if self.brief else ""
    prefix = self.data.format_prefix("[{}] ")
    return f"{prefix}{COMMAND_PREFIX}{self.names[0]}{brief}"

  def format_detail(self, header: bool = True) -> str:
    segments = list[str]()
    if header:
      prefix = self.data.format_prefix("{} | ")
      segments.append(f"「{prefix}{self.names[0]}」{self.brief}")
      segments.append(SEPARATOR)
    usage = self.usage() if isinstance(self.usage, Callable) else self.usage
    usage = usage.replace("__cmd__", self.names[0])
    segments.append(usage or "没有用法说明")
    if len(self.names) > 1:
      segments.append(SEPARATOR)
      segments.append("该命令有以下别名：" + "、".join(self.names[1:]))
    return "\n".join(segments)


class CategoryItem(Item):
  ROOT: ClassVar["CategoryItem"]

  name: str
  brief: str
  items: list[Item]
  _subcategorie: dict[str, "CategoryItem"]

  def __init__(self, name: str, brief: str = "", data: CommonData | None = None) -> None:
    super().__init__(data)
    self.name = name
    self.brief = brief
    self.items = []
    self._subcategorie = {}

  def add(self, item: Item) -> None:
    if isinstance(item, CategoryItem):
      if item.name in self._subcategorie:
        raise ValueError(f"重复的子分类名: {item.name}")
      self._subcategorie[item.name] = item
    item.parent = self
    self.items.append(item)

  def remove(self, item: Item) -> None:
    self.items.remove(item)
    if isinstance(item, CategoryItem):
      del self._subcategorie[item.name]
    item.parent = None

  def remove_user_items(self) -> None:
    remove_items = [item for item in self.items if isinstance(item, UserItem)]
    for item in remove_items:
      item.remove_self()
    for category in self._subcategorie.values():
      category.remove_user_items()

  @classmethod
  def find(
    cls,
    path: str | list[str],
    create: bool = False,
    ctx: Context | None = None,
  ) -> "CategoryItem":
    current = cls.ROOT
    if ctx and not current.check(ctx):
      raise ValueError("根分类不能显示")
    if isinstance(path, str):
      path = [x for x in path.split(".") if x]
    for i, name in enumerate(path, 1):
      if name not in current._subcategorie:
        if not create:
          raise KeyError(f"子分类 {'.'.join(path[:i])} 不存在")
        subcategory = cls(name)
        current.add(subcategory)
        current = subcategory
      else:
        current = current._subcategorie[name]
        if ctx and not current.check(ctx):
          raise ValueError(f"子分类 {'.'.join(path[:i])} 不能显示")
    return current

  @property
  @override
  def order(self) -> int:
    return -2

  @override
  def get_sort_key(self) -> list[str]:
    return get_sort_key(self.name)

  @override
  def format_title(self) -> str:
    brief = f" - {self.brief}" if self.brief else ""
    return f"📁{self.name}{brief}"

  def get_items(self, ctx: Context) -> list[Item]:
    items = [item for item in self.items if item.check(ctx)]
    items.sort(key=lambda item: (-item.data.priority, item.order, item.get_sort_key()))
    return items

  def get_path(self) -> str:
    parents = list[CategoryItem]()
    current = self
    while current:
      parents.append(current)
      current = current.parent
    parents.pop()  # 弹出根分类
    return ".".join(category.name for category in reversed(parents))

  def format_page(self, page: int, ctx: Context) -> tuple[str, int, int]:
    items = self.get_items(ctx)
    if not items:
      return "当前分类没有内容", 0, 0
    config = CONFIG()
    total_pages = math.ceil(len(items) / config.page_size)
    page = max(min(page, total_pages - 1), 0)
    items = items[config.page_size * page : config.page_size * (page + 1)]
    has_command = False
    has_category = False
    lines: list[str] = []
    for item in items:
      if isinstance(item, CommandItem):
        has_command = True
      elif isinstance(item, CategoryItem):
        has_category = True
      lines.append(item.format_title())
    lines.append(SEPARATOR)
    lines.append(f"第 {page + 1} 页，共 {total_pages} 页")
    header_lines: list[str] = []
    if has_command:
      header_lines.append(
        f"ℹ 「{COMMAND_PREFIX}」开头的是命令，"
        f"发送「{COMMAND_PREFIX}帮助 <命令名>」查看，"
        f"比如假设有「{COMMAND_PREFIX}某个命令」，"
        f"就需要发送「{COMMAND_PREFIX}帮助 某个命令」来查看",
      )
    if has_category:
      path = self.get_path()
      header_lines.append(
        f"ℹ 文件夹「📁」开头的是分类，"
        f"发送「{COMMAND_PREFIX}帮助 {path}<分类名>」查看，"
        f"比如假设有「📁某个分类」，"
        f"就需要发送「{COMMAND_PREFIX}帮助 {path}某个分类」来查看",
      )
    if header_lines:
      lines = [*header_lines, SEPARATOR, *lines]
    return "\n".join(lines), page, total_pages

  def format_forward(self, ctx: Context) -> list[str]:
    items = self.get_items(ctx)
    if not items:
      return ["当前分类没有内容"]
    config = CONFIG()
    has_command = False
    has_category = False
    nodes: list[str] = []
    for chunk in batched(items, config.page_size):
      lines: list[str] = []
      for item in chunk:
        if isinstance(item, CommandItem):
          has_command = True
        elif isinstance(item, CategoryItem):
          has_category = True
        lines.append(item.format_title())
      nodes.append("\n".join(lines))
    header_lines: list[str] = []
    if has_command:
      header_lines.append(
        f"ℹ 「{COMMAND_PREFIX}」开头的是命令，"
        f"发送「{COMMAND_PREFIX}帮助 <命令名>」查看，"
        f"比如假设有「{COMMAND_PREFIX}某个命令」，"
        f"就需要发送「{COMMAND_PREFIX}帮助 某个命令」来查看",
      )
    if has_category:
      path = self.get_path()
      header_lines.append(
        f"ℹ 文件夹「📁」开头的是分类，"
        f"发送「{COMMAND_PREFIX}帮助 {path}<分类名>」查看，"
        f"比如假设有「📁某个分类」，"
        f"就需要发送「{COMMAND_PREFIX}帮助 {path}某个分类」来查看",
      )
    if header_lines:
      return ["\n".join(header_lines), *nodes]
    return nodes


CategoryItem.ROOT = CategoryItem("root")


class UserStringItem(StringItem):
  pass


class UserCommandItem(CommandItem):
  pass


class UserCategoryItem(CategoryItem):
  pass


UserItem = UserStringItem | UserCommandItem | UserCategoryItem
