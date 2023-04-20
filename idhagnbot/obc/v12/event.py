from typing import List, Literal, Union

from idhagnbot.obc.model import Model
from idhagnbot.obc.v12.message import Message


class BotSelf(Model):
  platform: str
  user_id: str


class Version(Model):
  impl: str
  version: str
  onebot_version: str


class BotStatus(Model):
  self: BotSelf
  online: bool


class Status(Model):
  good: bool
  bots: List[BotStatus]


class Event(Model):
  id: str
  time: float
  type: str
  detail_type: str
  sub_type: str


class MetaEvent(Event):
  type: Literal["meta"]


class ConnectEvent(MetaEvent):
  detail_type: Literal["connect"]
  version: Version


class HeartbeatEvent(MetaEvent):
  detail_type: Literal["heartbeat"]
  interval: int


class StatusUpdateEvent(MetaEvent):
  detail_type: Literal["status_update"]
  status: Status


class BotEvent(Event):
  self: BotSelf


class MessageEvent(BotEvent):
  type: Literal["message"]
  message_id: str
  message: Message
  alt_message: str


class MessagePrivateEvent(MessageEvent):
  detail_type: Literal["private"]
  user_id: str


class MessageGroupEvent(MessageEvent):
  detail_type: Literal["group"]
  group_id: str
  user_id: str


class MessageChannelEvent(MessageEvent):
  detail_type: Literal["channel"]
  guild_id: str
  channel_id: str
  user_id: str


class NoticeEvent(BotEvent):
  type: Literal["notice"]


class FriendIncreaseEvent(NoticeEvent):
  detail_type: Literal["friend_increase"]
  user_id: str


class FriendDecreaseEvent(NoticeEvent):
  detail_type: Literal["friend_decrease"]
  user_id: str


class PrivateMessageDeleteEvent(NoticeEvent):
  detail_type: Literal["private_message_delete"]
  user_id: str
  message_id: str


class GroupMemberIncreaseEvent(NoticeEvent):
  detail_type: Literal["group_member_increase"]
  sub_type: Union[Literal["join", "invite", ""], str]
  group_id: str
  user_id: str
  operator_id: str


class GroupMemberDecreaseEvent(NoticeEvent):
  detail_type: Literal["group_member_decrease"]
  sub_type: Union[Literal["leave", "kick", ""], str]
  group_id: str
  user_id: str
  operator_id: str


class GroupMessageDeleteEvent(NoticeEvent):
  detail_type: Literal["group_message_delete"]
  group_id: str
  user_id: str
  operator_id: str
  message_id: str


class GuildMemberIncreaseEvent(NoticeEvent):
  detail_type: Literal["guild_member_increase"]
  sub_type: Union[Literal["join", "invite", ""], str]
  guild_id: str
  user_id: str
  operator_id: str


class GuildMemberDecreaseEvent(NoticeEvent):
  detail_type: Literal["guild_member_decrease"]
  sub_type: Union[Literal["leave", "kick", ""], str]
  guild_id: str
  user_id: str
  operator_id: str


class ChannelMemberIncreaseEvent(NoticeEvent):
  detail_type: Literal["channel_member_increase"]
  sub_type: Union[Literal["join", "invite", ""], str]
  guild_id: str
  channel_id: str
  user_id: str
  operator_id: str


class ChannelMemberDecreaseEvent(NoticeEvent):
  detail_type: Literal["channel_member_decrease"]
  sub_type: Union[Literal["leave", "kick", ""], str]
  guild_id: str
  channel_id: str
  user_id: str
  operator_id: str


class ChannelMessageDeleteEvent(NoticeEvent):
  detail_type: Literal["channel_message_delete"]
  guild_id: str
  channel_id: str
  user_id: str
  operator_id: str


class ChannelCreateEvent(NoticeEvent):
  detail_type: Literal["channel_create"]
  guild_id: str
  channel_id: str
  operator_id: str


class ChannelDeleteEvent(NoticeEvent):
  detail_type: Literal["channel_delete"]
  guild_id: str
  channel_id: str
  operator_id: str


class RequestEvent(BotEvent):
  type: Literal["request"]


MetaEventStd = Union[
  ConnectEvent,
  HeartbeatEvent,
  StatusUpdateEvent,
]
MessageEventStd = Union[
  MessagePrivateEvent,
  MessageGroupEvent,
  MessageChannelEvent,
]
NoticeEventStd = Union[
  FriendIncreaseEvent,
  FriendDecreaseEvent,
  PrivateMessageDeleteEvent,
  GroupMemberIncreaseEvent,
  GroupMemberDecreaseEvent,
  GroupMessageDeleteEvent,
  GuildMemberIncreaseEvent,
  GuildMemberDecreaseEvent,
  ChannelMemberIncreaseEvent,
  ChannelMemberDecreaseEvent,
  ChannelMessageDeleteEvent,
  ChannelCreateEvent,
  ChannelDeleteEvent,
]
EventStd = Union[
  MetaEventStd,
  MessageEventStd,
  NoticeEventStd,
]
# 事件基本类型不可拓展
EventAny = Union[
  EventStd,
  MetaEvent,
  MessageEvent,
  NoticeEvent,
  RequestEvent,
]
