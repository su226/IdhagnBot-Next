from collections import deque
from enum import Enum
from heapq import nlargest
from typing import Annotated, Any, Iterable, Union, cast

import nonebot
from nonebot.params import Depends
from nonebot.permission import Permission
from pydantic import BaseModel, Field, PrivateAttr
from pygtrie import StringTrie  # type: ignore

nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import SceneType, Session, Uninfo

Node = tuple[str, ...]


def parse_node(value: str) -> Node:
  return tuple(filter(None, value.split(".")))


class NodeTrie(StringTrie):
  def __init__(self, *args: Any, **kw: Any):
    super().__init__(separator=".", *args, **kw)

  def _path_from_key(self, key: Union[str, Node]) -> Iterable[str]:
    if isinstance(key, str):
      return parse_node(key)
    return key


class Entry(BaseModel):
  node: str
  value: bool


class Role(BaseModel):
  priority: int = 0
  parents: set[str] = Field(default_factory=set)
  entries: list[Entry] = Field(default_factory=list)
  _tree: NodeTrie = PrivateAttr()

  def __init__(self, **kw: Any) -> None:
    super().__init__(**kw)
    self._tree = NodeTrie()
    for entry in self.entries:
      self._tree[entry.node] = entry


class Config(BaseModel):
  roles: dict[str, Role] = Field(default_factory=dict)


class ConfigWrapper(BaseModel):
  idhagnbot_permission: Config = Config()


config = nonebot.get_plugin_config(ConfigWrapper).idhagnbot_permission


def is_superuser(adapter: str, user_id: str) -> bool:
  driver = nonebot.get_driver()
  adapter = adapter.split(maxsplit=1)[0].lower()
  return f"{adapter}:{user_id}" in driver.config.superusers or user_id in driver.config.superusers


def get_roles(session: Session) -> set[str]:
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  queue = deque(["default", scope, f"{scope}_user_{session.user.id}"])
  if is_superuser(session.adapter, session.user.id):
    queue.extend(["superuser", f"{scope}_superuser"])
  if session.scene.type == SceneType.GROUP:
    queue.extend(["group", f"{scope}_group", f"{scope}_group_{session.scene.id}"])
    if session.member and session.member.role:
      role = session.member.role.id.lower()
      queue.extend([role, f"{scope}_{role}", f"{scope}_group_{session.scene.id}_{role}"])
  elif session.scene.type == SceneType.PRIVATE:
    queue.extend(["private", f"{scope}_private", f"{scope}_private_{session.scene.id}"])
  # TODO: 二级群组（GUILD、CHANNEL）
  roles = set()
  while queue:
    i = queue.popleft()
    if i in roles:
      continue
    roles.add(i)
    if i in config.roles:
      queue.extend(config.roles[i].parents)
  return roles


def walk_most(trie: NodeTrie, key: Node) -> Iterable[NodeTrie._Step]:
  try:
    yield from trie.walk_towards(key)
  except KeyError:
    pass


def check(node: Node, roles: list[str], default_grant_to: set[str]) -> bool:
  values: list[tuple[int, int, bool]] = []
  for priority, role in enumerate(roles):
    if role in default_grant_to:
      values.append((priority, len(node), True))
    if role in config.roles:
      for specificity, step in enumerate(walk_most(config.roles[role]._tree, node)):
        if step.is_set:
          values.append((priority, specificity, cast(Entry, step.value).value))
  if not values:
    return False
  return nlargest(1, values)[0][2]


def get_role_priority(role: str) -> int:
  if role in config.roles:
    return config.roles[role].priority
  return 0


def roles(session: Uninfo) -> list[str]:
  roles = list(get_roles(session))
  roles.sort(key=get_role_priority)
  return roles


Roles = Annotated[list[str], Depends(roles)]


def permission(node_str: str, default_grant_to: set[str] = {"default"}) -> Permission:
  def checker(roles: Roles) -> bool:
    return check(node, roles, default_grant_to)

  node = parse_node(node_str)
  return Permission(checker)
