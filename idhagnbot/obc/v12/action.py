from typing import Any, List, Literal, Optional, Union

from pydantic import validator

from idhagnbot.obc.model import Model
from idhagnbot.obc.v12.event import BotSelf, EventAny, Status, Version
from idhagnbot.obc.v12.message import Message


class ActionRequest(Model):
  action: str
  params: Any
  echo: Optional[str]
  self: Optional[BotSelf]


class ActionResponse(Model):
  status: Literal["ok", "failed"]
  retcode: int
  data: Any
  message: str
  echo: Optional[str]


class GetLatestEventsParam(Model):
  limit: int
  timeout: int


GetLatestEventsResult = List[EventAny]
GetSupportedActionsParam = Model
GetSupportedActionsResult = List[str]
GetStatusParam = Model
GetStatusResult = Status
GetVersionParam = Model
GetVersionResult = Version


class SendMessageBaseParam(Model):
  detail_type: str
  message: Message


class SendMessagePrivateParam(SendMessageBaseParam):
  detail_type: Literal["private"]
  user_id: str


class SendMessageGroupParam(SendMessageBaseParam):
  detail_type: Literal["group"]
  group_id: str


class SendMessageChannelParam(SendMessageBaseParam):
  detail_type: Literal["channel"]
  guild_id: str
  channel_id: str

class SendMessageCustomParam(SendMessageBaseParam):
  @validator("detail_type")
  def check_detail_type(cls, v: str) -> str:
    if v in {"private", "group", "channel"}:
      raise ValueError(f"{v} is a standard OneBot type.")
    return v


SendMessageStdParam = Union[
  SendMessagePrivateParam,
  SendMessageGroupParam,
  SendMessageChannelParam,
]
SendMessageParam = Union[
  SendMessageStdParam,
  SendMessageCustomParam,
]


class SendMessageResult(Model):
  message_id: str
  time: float


class DeleteMessageParam(Model):
  message_id: str


DeleteMessageResult = Model
GetSelfInfoParam = Model


class GetSelfInfoResult(Model):
  user_id: str
  user_name: str
  user_displayname: str


class GetUserInfoParam(Model):
  user_id: str


class GetUserInfoResult(GetSelfInfoResult):
  user_remark: str


GetFriendListParam = Model
GetFriendListResult = List[GetUserInfoResult]


class GetGroupInfoParam(Model):
  group_id: str


class GetGroupInfoResult(Model):
  group_id: str
  group_name: str


GetGroupListParam = Model
GetGroupListResult = List[GetGroupInfoResult]


class GetGroupMemberInfoParam(Model):
  group_id: str
  user_id: str


GetGroupMemberInfoResult = GetSelfInfoResult
GetGroupMemberListParam = GetGroupInfoParam
GetGroupMemberListResult = List[GetGroupMemberInfoResult]


class SetGroupNameParam(Model):
  group_id: str
  group_name: str


SetGroupNameResult = Model
LeaveGroupParam = GetGroupInfoParam
LeaveGroupResult = Model


class GetGuildInfoParam(Model):
  guild_id: str


class GetGuildInfoResult(Model):
  guild_id: str
  guild_name: str


GetGuildListParam = Model
GetGuildListResult = List[GetGuildInfoResult]


class GetGuildMemberInfoParam(Model):
  guild_id: str
  user_id: str


GetGuildMemberInfoResult = GetSelfInfoResult
GetGuildMemberListParam = GetGuildInfoParam
GetGuildMemberListResult = List[GetGuildMemberInfoResult]


class SetGuildNameParam(Model):
  guild_id: str
  guild_name: str


SetGuildNameResult = Model
LeaveGuildParam = GetGuildInfoParam
LeaveGuildResult = Model


class GetChannelInfoParam(Model):
  guild_id: str
  channel_id: str


class GetChannelInfoResult(Model):
  channel_id: str
  channel_name: str


class GetChannelListParam(Model):
  guild_id: str
  joined_only: bool


GetChannelListResult = List[GetChannelInfoResult]


class GetChannelMemberInfoParam(Model):
  guild_id: str
  user_id: str


GetChannelMemberInfoResult = GetSelfInfoResult
GetChannelMemberListParam = GetChannelInfoParam
GetChannelMemberListResult = List[GetChannelMemberInfoResult]


class SetChannelNameParam(Model):
  guild_id: str
  channel_id: str
  guild_name: str


SetChannelNameResult = Model
LeaveChannelParam = GetChannelInfoParam
LeaveChannelResult = Model
