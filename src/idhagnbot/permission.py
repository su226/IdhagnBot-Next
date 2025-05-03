import re
from collections import deque
from collections.abc import Iterable
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union, cast

import nonebot
from nonebot.params import Depends
from nonebot.permission import Permission
from pydantic import BaseModel, Field, PrivateAttr
from pygtrie import StringTrie

from idhagnbot.config import SharedConfig

nonebot.require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import SceneType, Uninfo

Node = tuple[str, ...]
Value = Union[bool, Literal["default"]]


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
  value: Value


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
CHANNEL_TYPES = {
  SceneType.CHANNEL_CATEGORY: "category",
  SceneType.CHANNEL_TEXT: "text",
  SceneType.CHANNEL_VOICE: "voice",
}
PLATFORM_USER_RE = re.compile(r"^(?P<platform>[^:]+):user:(?P<user>[^:]+)$")
PLATFORM_GUILD_ID_CHANNEL_ROLE_RE = re.compile(r"^(?P<platform>[^:]+):guild:(?P<guild>[^:]+):channel:(?P<channel>[^:]+):(?P<role>member|administrator|owner)$")  # noqa: E501
PLATFORM_GUILD_ID_TYPE_ROLE_RE = re.compile(r"^(?P<platform>[^:]+):guild:(?P<guild>[^:]+):(?P<type>category|text|voice):(?P<role>member|administrator|owner)$")  # noqa: E501
PLATFORM_GUILD_ID_CHANNEL_RE = re.compile(r"^(?P<platform>[^:]+):guild:(?P<guild>[^:]+):channel:(?P<channel>[^:]+)$")  # noqa: E501
PLATFORM_GUILD_ID_TYPE_RE = re.compile(r"^(?P<platform>[^:]+):guild:(?P<guild>[^:]+):(?P<type>category|text|voice)$")  # noqa: E501
PLATFORM_TYPE_ID_ROLE_RE = re.compile(r"^(?P<platform>[^:]+):(?P<type>group|guild):(?P<id>[^:]+):(?P<role>member|administrator|owner)$")  # noqa: E501
PLATFORM_TYPE_ROLE_RE = re.compile(r"^(?P<platform>[^:]+):(?P<type>group|guild)_(?P<role>member|administrator|owner)$")  # noqa: E501
PLATFORM_TYPE_ID_RE = re.compile(r"^(?P<platform>[^:]+):(?P<type>private|group|guild):(?P<user>[^:]+)$")  # noqa: E501
PLATFORM_TYPE_RE = re.compile(r"^(?P<platform>[^:]+):(?P<type>superuser|private|group|guild|text|voice|category|member|administrator|owner)$")  # noqa: E501
TYPE_ROLE_RE = re.compile(r"^(?P<type>group|guild)_(?P<role>member|administrator|owner)$")
SUPERUSER = {"superuser"}
OWNER_OR_ABOVE = {"owner"} | SUPERUSER
ADMINISTRATOR_OR_ABOVE = {"administrator"} | OWNER_OR_ABOVE
DEFAULT = {"default"}


def get_role_parents(role: str) -> set[str]:
  config = CONFIG()
  parents = config.roles[role].parents if role in config.roles else None
  if parents is not None:
    return parents
  if match := PLATFORM_USER_RE.match(role):
    return {match["platform"]}
  if match := PLATFORM_GUILD_ID_CHANNEL_ROLE_RE.match(role):
    return {
      f"{match['platform']}:guild:{match['guild']}:channel:{match['channel']}",
      f"{match['platform']}:guild:{match['guild']}:{match['role']}",
    }
  if match := PLATFORM_GUILD_ID_TYPE_ROLE_RE.match(role):
    return {
      f"{match['platform']}:guild:{match['guild']}:{match['type']}",
      f"{match['platform']}:guild:{match['guild']}:{match['role']}",
    }
  if match := PLATFORM_GUILD_ID_CHANNEL_RE.match(role):
    return {f"{match['platform']}:guild:{match['guild']}"}
  if match := PLATFORM_GUILD_ID_TYPE_RE.match(role):
    return {f"{match['platform']}:guild:{match['guild']}", f"{match['platform']}:{match['type']}"}
  if match := PLATFORM_TYPE_ID_ROLE_RE.match(role):
    return {
      f"{match['platform']}:{match['type']}:{match['id']}",
      f"{match['platform']}:{match['type']}_{match['role']}",
    }
  if match := PLATFORM_TYPE_ROLE_RE.match(role):
    return {
      f"{match['platform']}:{match['type']}",
      f"{match['platform']}:{match['role']}",
      f"{match['type']}_{match['role']}",
    }
  if match := PLATFORM_TYPE_ID_RE.match(role):
    return {f"{match['platform']}:{match['type']}"}
  if match := PLATFORM_TYPE_RE.match(role):
    return {match["platform"], match["type"]}
  if match := TYPE_ROLE_RE.match(role):
    return {match["type"], match["role"]}
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
  elif session.scene.type in CHANNEL_TYPES and session.scene.parent:
    role = session.member.role.id.lower() if session.member and session.member.role else "member"
    channel_type = CHANNEL_TYPES[session.scene.type]
    queue.append(f"{scope}:guild:{session.scene.parent.id}:channel:{session.scene.id}:{role}")
    queue.append(f"{scope}:guild:{session.scene.parent.id}:{channel_type}:{role}")
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
  values: list[tuple[int, int, Value]] = []
  for priority, role in enumerate(sorted_roles):
    if role in config.roles:
      for specificity, step in enumerate(config.roles[role]._tree.walk_most(node)):
        if step.is_set:
          values.append((priority, specificity, cast(Entry, step.value).value))
  value = max(values, key=lambda x: x[:2])[2] if values else "default"
  return any(role in default_grant_to for role in sorted_roles) if value == "default" else value


def permission(node_str: str, default_grant_to: set[str] = DEFAULT) -> Permission:
  def checker(roles: SortedRoles) -> bool:
    return check(node, roles, default_grant_to)

  node = parse_node(node_str)
  return Permission(checker)
