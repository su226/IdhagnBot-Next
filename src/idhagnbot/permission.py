from collections.abc import Iterable
from enum import Enum
from typing import Annotated, Any, Literal, cast

import nonebot
from nonebot.params import Depends
from nonebot.permission import Permission
from pydantic import BaseModel, Field, PrivateAttr
from pygtrie import StringTrie  # pyright: ignore[reportMissingTypeStubs]
from typing_extensions import override

from idhagnbot.config import SharedConfig

nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import SceneType, Uninfo

Node = tuple[str, ...]
Value = bool | Literal["default"]


def parse_node(value: str) -> Node:
  return tuple(filter(None, value.split(".")))


class NodeTrie(StringTrie):
  def __init__(self, *args: Any, **kw: Any) -> None:
    super().__init__(*args, separator=".", **kw)

  @override
  def _path_from_key(self, key: str | Node) -> Iterable[str]:
    if isinstance(key, str):
      return parse_node(key)
    return key

  def walk_most(self, key: Node) -> Iterable["NodeTrie._Step"]:
    try:
      yield from self.walk_towards(key)
    except KeyError:
      pass


class Entry(BaseModel):
  node: str
  value: Value


class Rule(BaseModel):
  selectors: list[set[str]] = Field(default_factory=list)
  entries: list[Entry] = Field(default_factory=list)
  _tree: NodeTrie = PrivateAttr()

  def selectors_match(self, roles: set[str]) -> bool:
    return any(selector <= roles for selector in self.selectors)

  def __init__(self, **kw: Any) -> None:
    super().__init__(**kw)
    self._tree = NodeTrie()
    for entry in self.entries:
      self._tree[entry.node] = entry

  @property
  def tree(self) -> NodeTrie:
    return self._tree


class Config(BaseModel):
  rules: list[Rule] = Field(default_factory=list)


CONFIG = SharedConfig("permission", Config)
CHANNEL_TYPES = {
  SceneType.CHANNEL_CATEGORY: "category",
  SceneType.CHANNEL_TEXT: "text",
  SceneType.CHANNEL_VOICE: "voice",
}
SUPERUSER = {"superuser"}
OWNER_OR_ABOVE = {"owner"} | SUPERUSER
ADMINISTRATOR_OR_ABOVE = {"administrator"} | OWNER_OR_ABOVE
DEFAULT = {"default"}


def is_superuser(adapter: str, user_id: str) -> bool:
  driver = nonebot.get_driver()
  adapter = adapter.split(maxsplit=1)[0].lower()
  return f"{adapter}:{user_id}" in driver.config.superusers or user_id in driver.config.superusers


def get_roles(session: Uninfo) -> set[str]:
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  adapter = session.adapter._name_ if isinstance(session.adapter, Enum) else session.adapter
  roles = {"default", scope, adapter, f"user_{session.user.id}"}
  if is_superuser(session.adapter, session.user.id):
    roles.add("superuser")
  if session.scene.type == SceneType.GROUP:
    role = session.member.role.id.lower() if session.member and session.member.role else "member"
    roles.add("group")
    roles.add(role)
    roles.add(f"group_{session.scene.id}")
  elif session.scene.type == SceneType.PRIVATE:
    roles.add("private")
  elif session.scene.type in CHANNEL_TYPES and session.scene.parent:
    role = session.member.role.id.lower() if session.member and session.member.role else "member"
    channel_type = CHANNEL_TYPES[session.scene.type]
    roles.add("guild")
    roles.add(channel_type)
    roles.add(role)
    roles.add(f"guild_{session.scene.parent.id}")
    roles.add(f"channel_{session.scene.id}")
  return roles


Roles = Annotated[set[str], Depends(get_roles)]


def check(node: Node, roles: set[str], default_grant_to: set[str]) -> bool:
  config = CONFIG()
  values: list[tuple[int, int, Value]] = []
  for priority, rule in enumerate(config.rules):
    if rule.selectors_match(roles):
      last = None
      for specificity, step in enumerate(rule.tree.walk_most(node)):
        if step.is_set:
          last = (priority, specificity, cast(Entry, step.value).value)
      if last:
        values.append(last)
  value = max(values, key=lambda x: x[:2])[2] if values else "default"
  return any(role in default_grant_to for role in roles) if value == "default" else value


def permission(node_str: str, default_grant_to: set[str] = DEFAULT) -> Permission:
  def checker(roles: Roles) -> bool:
    return check(node, roles, default_grant_to)

  node = parse_node(node_str)
  return Permission(checker)
