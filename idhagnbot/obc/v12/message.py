from typing import Any, List, Literal, Union, Dict

from pydantic import validator, parse_obj_as
from idhagnbot.obc.model import Model


class DataText(Model):
  text: str


class DataUserId(Model):
  user_id: str


class DataFileId(Model):
  file_id: str


class DataReply(Model):
  user_id: str = ""  # user_id 对于发送可选
  message_id: str


class DataLocation(Model):
  latitude: float
  longitude: float
  title: str
  content: str


class SegmentBase(Model):
  type: str
  data: Model

  @staticmethod
  def text(text: str, *data: Dict[str, Any], **kw: Any) -> "SegmentText":
    for d in data:
      kw.update(d)
    return SegmentText(type="text", data=DataText(text=text, **kw))

  @staticmethod
  def mention(user_id: str, *data: Dict[str, Any], **kw: Any) -> "SegmentMention":
    for d in data:
      kw.update(d)
    return SegmentMention(type="mention", data=DataUserId(user_id=user_id, **kw))

  @staticmethod
  def mention_all(*data: Dict[str, Any], **kw: Any) -> "SegmentMentionAll":
    for d in data:
      kw.update(d)
    return SegmentMentionAll(type="mention_all", data=Model(**kw))

  @staticmethod
  def image(file_id: str, *data: Dict[str, Any], **kw: Any) -> "SegmentImage":
    for d in data:
      kw.update(d)
    return SegmentImage(type="image", data=DataFileId(file_id=file_id, **kw))

  @staticmethod
  def voice(file_id: str, *data: Dict[str, Any], **kw: Any) -> "SegmentVoice":
    for d in data:
      kw.update(d)
    return SegmentVoice(type="voice", data=DataFileId(file_id=file_id, **kw))

  @staticmethod
  def audio(file_id: str, *data: Dict[str, Any], **kw: Any) -> "SegmentAudio":
    for d in data:
      kw.update(d)
    return SegmentAudio(type="audio", data=DataFileId(file_id=file_id, **kw))

  @staticmethod
  def video(file_id: str, *data: Dict[str, Any], **kw: Any) -> "SegmentVideo":
    for d in data:
      kw.update(d)
    return SegmentVideo(type="video", data=DataFileId(file_id=file_id, **kw))

  @staticmethod
  def file(file_id: str, *data: Dict[str, Any], **kw: Any) -> "SegmentFile":
    for d in data:
      kw.update(d)
    return SegmentFile(type="file", data=DataFileId(file_id=file_id, **kw))

  @staticmethod
  def location(
    latitude: float,
    longitude: float,
    title: str,
    content: str,
    *data: Dict[str, Any],
    **kw: Any,
  ) -> "SegmentLocation":
    for d in data:
      kw.update(d)
    return SegmentLocation(type="location", data=DataLocation(
      latitude=latitude,
      longitude=longitude,
      title=title,
      content=content,
      **kw,
    ))

  @staticmethod
  def reply(message_id: str, user_id: str, *data: Dict[str, Any], **kw: Any) -> "SegmentReply":
    for d in data:
      kw.update(d)
    return SegmentReply(type="reply", data=DataReply(
      message_id=message_id,
      user_id=user_id,
      **kw,
    ))

  @staticmethod
  def custom(type: str, *data: Dict[str, Any], **kw: Any) -> "Segment":
    for d in data:
      kw.update(d)
    return parse_obj_as(Segment, SegmentBase(type=type, data=Model(**kw)))


class SegmentText(SegmentBase):
  type: Literal["text"]
  data: DataText


class SegmentMention(SegmentBase):
  type: Literal["mention"]
  data: DataUserId


class SegmentMentionAll(SegmentBase):
  type: Literal["mention_all"]


class SegmentImage(SegmentBase):
  type: Literal["image"]
  data: DataFileId


class SegmentVoice(SegmentBase):
  type: Literal["voice"]
  data: DataFileId


class SegmentAudio(SegmentBase):
  type: Literal["audio"]
  data: DataFileId


class SegmentVideo(SegmentBase):
  type: Literal["video"]
  data: DataFileId


class SegmentFile(SegmentBase):
  type: Literal["file"]
  data: DataFileId


class SegmentLocation(SegmentBase):
  type: Literal["location"]
  data: DataLocation


class SegmentReply(SegmentBase):
  type: Literal["reply"]
  data: DataReply


class SegmentOther(SegmentBase):
  @validator("type")
  def check_type(cls, v: str) -> str:
    if v in {
      "text",
      "mention",
      "mention_all",
      "image",
      "voice",
      "audio",
      "video",
      "file",
      "location",
      "reply"
    }:
      raise ValueError(f"{v} is a standard OneBot segment.")
    return v


SegmentStd = Union[
  SegmentText,
  SegmentMention,
  SegmentMentionAll,
  SegmentImage,
  SegmentVoice,
  SegmentAudio,
  SegmentVideo,
  SegmentFile,
  SegmentLocation,
  SegmentReply,
]
Segment = Union[SegmentStd, SegmentOther]
Message = List[Segment]
