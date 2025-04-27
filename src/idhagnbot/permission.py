import re
from collections import deque
from collections.abc import Iterable
from enum import Enum
from typing import Annotated, Any, Optional, Union, cast

import nonebot
from nonebot.params import Depends
from nonebot.permission import Permission
from pydantic import BaseModel, Field, PrivateAttr
from pygtrie import StringTrie

from idhagnbot.config import SharedConfig

nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import SceneType, Uninfo

Node = tuple[str, ...]


def parse_node(value: str) -> Node:
  return tuple(filter(None, value.split(".")))


class NodeTrie(StringTrie):
  def __init__(self, *args: Any, **kw: Any) -> None:
    super().__init__(*args, separator=".", **kw)

  def _path_from_key(self, key: Union[str, Node]) -> Iterable[str]:
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
  value: bool


class Role(BaseModel):
  priority: Optional[int] = None
  parents: Optional[set[str]] = Field(default_factory=set)
  entries: list[Entry] = Field(default_factory=list)
  _tree: NodeTrie = PrivateAttr()

  def __init__(self, **kw: Any) -> None:
    super().__init__(**kw)
    self._tree = NodeTrie()
    for entry in self.entries:
      self._tree[entry.node] = entry


class Config(BaseModel):
  roles: dict[str, Role] = Field(default_factory=dict)


CONFIG = SharedConfig("permission", Config)
USER_RE = re.compile(r"^(?P<platform>[^:]+):user:(?P<user>[^:]+)$")
SUPERUSER_RE = re.compile(r"^(?P<platform>[^:]+):superuser$")
GROUP_ID_ROLE_RE = re.compile(r"^(?P<platform>[^:]+):group:(?P<group>[^:]+):(?P<role>member|administrator|owner)$")  # noqa: E501
GROUP_ID_RE = re.compile(r"^(?P<platform>[^:]+):group:(?P<group>[^:]+)$")
GROUP_RE = re.compile(r"^(?P<platform>[^:]+):group$")
ROLE_RE = re.compile(r"^(?P<platform>[^:]+):(?P<role>member|administrator|owner)$")
PRIVATE_ID_RE = re.compile(r"^(?P<platform>[^:]+):private:(?P<user>[^:]+)$")
PRIVATE_RE = re.compile(r"^(?P<platform>[^:]+):private$")


def get_role_parents(role: str) -> set[str]:
  config = CONFIG()
  parents = config.roles[role].parents if role in config.roles else None
  if parents is not None:
    return parents
  if match := USER_RE.match(role):
    return {match["platform"]}
  if match := SUPERUSER_RE.match(role):
    return {match["platform"], "superuser"}
  if match := GROUP_ID_ROLE_RE.match(role):
    return {f"{match['platform']}:group:{match['group']}", f"{match['platform']}:{match['role']}"}
  if match := GROUP_ID_RE.match(role):
    return {f"{match['platform']}:group"}
  if match := GROUP_RE.match(role):
    return {match["platform"]}
  if match := ROLE_RE.match(role):
    return {match["platform"], match["role"]}
  if match := PRIVATE_ID_RE.match(role):
    return {f"{match['platform']}:private"}
  if match := PRIVATE_RE.match(role):
    return {match["platform"]}
  if role == "default":
    return set()
  return {"default"}


def get_role_priority(role: str) -> int:
  config = CONFIG()
  priority = config.roles[role].priority if role in config.roles else None
  return priority or 0


def is_superuser(adapter: str, user_id: str) -> bool:
  driver = nonebot.get_driver()
  adapter = adapter.split(maxsplit=1)[0].lower()
  return f"{adapter}:{user_id}" in driver.config.superusers or user_id in driver.config.superusers


def get_roles(session: Uninfo) -> set[str]:
  scope = session.scope._name_ if isinstance(session.scope, Enum) else session.scope
  queue = deque([f"{scope}:user:{session.user.id}"])
  if is_superuser(session.adapter, session.user.id):
    queue.append(f"{scope}:superuser")
  if session.scene.type == SceneType.GROUP:
    role = session.member.role.id.lower() if session.member and session.member.role else "member"
    queue.append(f"{scope}:group:{session.scene.id}:{role}")
  elif session.scene.type == SceneType.PRIVATE:
    queue.append(f"{scope}:private:{session.scene.id}")
  # TODO: 二级群组（GUILD、CHANNEL）
  roles = set()
  while queue:
    i = queue.popleft()
    if i in roles:
      continue
    roles.add(i)
    queue.extend(get_role_parents(i))
  return roles


def get_sorted_roles(session: Uninfo) -> list[str]:
  return sorted(get_roles(session), key=lambda x: (get_role_priority(x), x))


Roles = Annotated[set[str], Depends(get_roles)]
SortedRoles = Annotated[list[str], Depends(get_sorted_roles)]


def check(node: Node, sorted_roles: list[str], default_grant_to: set[str]) -> bool:
  config = CONFIG()
  values: list[tuple[int, int, bool]] = []
  is_set = False
  for priority, role in enumerate(sorted_roles):
    if role in config.roles:
      for specificity, step in enumerate(config.roles[role]._tree.walk_most(node)):
        if step.is_set:
          is_set = True
          values.append((priority, specificity, cast(Entry, step.value).value))
  if not is_set:
    for priority, role in enumerate(sorted_roles):
      if role in default_grant_to:
        values.append((priority, len(node), True))
  if not values:
    return False
  return max(values)[2]


def permission(node_str: str, default_grant_to: Optional[set[str]] = None) -> Permission:
  def checker(roles: SortedRoles) -> bool:
    return check(node, roles, {"default"} if default_grant_to is None else default_grant_to)

  node = parse_node(node_str)
  return Permission(checker)
