import dataclasses
import sys
import uuid
from datetime import datetime
from enum import Enum
from typing import (
  Any, BinaryIO, ClassVar, Dict, Iterable, List, Literal, Optional, Protocol, Tuple, Union,
  runtime_checkable
)

from pydantic import Field, PrivateAttr
from pyrogram.enums import ChatType, MessageEntityType, MessageMediaType
from pyrogram.types import (
  Animation, Audio, Document, InputMediaAudio, InputMediaDocument, InputMediaPhoto,
  InputMediaVideo, Message as MessageTG, MessageEntity, Photo, Thumbnail, User, Video
)
from pyrogram.types.object import Object as TGObject

from idhagnbot.obc.model import Model
from idhagnbot.obc.v12.event import BotSelf, MessageEvent, MessageGroupEvent, MessagePrivateEvent
from idhagnbot.obc.v12.message import (
  DataFileId, DataLocation, DataReply, DataText, DataUserId, Message as MessageOB, SegmentAudio,
  SegmentBase, SegmentFile, SegmentImage, SegmentVideo
)


class DataTextExt(DataText):
  sub_type: Literal[
    # 可以手动发送的类型
    "text",
    "text_mention",
    "text_link",
    "code",
    "pre",
    # 不明
    "blockquote",
    "custom_emoji",
    # 不能手动发送，只能由 Telegram 自动识别的类型
    "mention",
    "hashtag",
    "cashtag",
    "command",
    "url",
    "email",
    "phone_number",
    "bank_card",
  ] = Field("text", alias="tg.sub_type")
  bold: bool = Field(False, alias="tg.bold")
  itailc: bool = Field(False, alias="tg.italic")
  strikethrough: bool = Field(False, alias="tg.strikethrough")
  spoiler: bool = Field(False, alias="tg.spoiler")
  url: str = Field("", alias="tg.url")
  language: str = Field("", alias="tg.language")
  custom_emoji_id: str = Field("", alias="tg.custom_emoji_id")


class DataMentionExt(DataUserId):
  text: str = Field("", alias="tg.text")
  bold: bool = Field(False, alias="tg.bold")
  itailc: bool = Field(False, alias="tg.italic")
  strikethrough: bool = Field(False, alias="tg.strikethrough")
  spoiler: bool = Field(False, alias="tg.spoiler")
  _user: Optional[User] = PrivateAttr(None)


class DataImageExt(DataFileId):
  sub_type: Literal["photo", "sticker"] = Field("photo", alias="tg.sub_type")
  spoiler: bool = Field(False, alias="tg.spoiler")


class DataVideoExt(DataFileId):
  sub_type: Literal["video", "animation", "video_note"] = Field("video", alias="tg.sub_type")
  spoiler: bool = Field(False, alias="tg.spoiler")


class DataLocationExt(DataLocation):
  sub_type: Optional[Literal["location", "venue"]] = Field(None, alias="tg.sub_type")
  foursquare_id: str = Field("", alias="tg.foursquare_id")
  foursquare_type: str = Field("", alias="tg.foursquare_address")


class DataSchedule(Model):
  time: int


class DataForward(Model):
  message_id: str
  no_media_group: bool = False


def _serialize_tgobject(obj: Any) -> Any:
  if isinstance(obj, list):
    return [_serialize_tgobject(x) for x in obj]
  elif isinstance(obj, TGObject):
    return {
      attr: _serialize_tgobject(value)
      for attr in obj.__dict__
      if not attr.startswith("_") and (value := getattr(obj, attr)) is not None
    }
  elif isinstance(obj, Enum):
    return obj.name.lower()
  else:
    return obj


if sys.version_info >= (3, 9):
  removeprefix = str.removeprefix
else:
  def removeprefix(s: str, prefix: str) -> str:
    if s.startswith(prefix):
      return s[len(prefix):]
    return s


def message_event_to_onebot(
  bot_self: BotSelf,
  message: MessageTG,
  media_group: Optional[List[MessageTG]] = None,
) -> MessageEvent:
  data = {
    "tg.protected": message.has_protected_content,
    "tg.media_group_id": message.media_group_id,
    "tg.original_events": None,
    "tg.user": _serialize_tgobject(message.from_user),
    "tg.chat": _serialize_tgobject(message.chat),
    "tg.sender_chat": _serialize_tgobject(message.sender_chat),
    "tg.forward_from": _serialize_tgobject(message.forward_from),
    "tg.forward_sender_name": message.forward_sender_name,
    "tg.forward_from_chat": _serialize_tgobject(message.forward_from_chat),
    "tg.forward_from_message_id": message.forward_from_message_id,
    "tg.forward_signature": message.forward_signature,
    "tg.forward_date": (
      None if message.forward_date is None else message.forward_date.timestamp()
    ),
    "tg.mentioned": message.mentioned,
    "tg.empty": message.empty,
    "tg.scheduled": message.scheduled,
    "tg.from_scheduled": message.from_scheduled,
    "tg.edit_date": None if message.edit_date is None else message.edit_date.timestamp(),
    "tg.author_signature": message.author_signature,
    "tg.views": message.views,
    "tg.forwards": message.forwards,
    "tg.via_bot": _serialize_tgobject(message.via_bot),
    "tg.outgoing": message.outgoing,
    "tg.reply_markup": _serialize_tgobject(message.reply_markup),
    "tg.reactions": _serialize_tgobject(message.reactions),
  }
  if media_group is not None:
    parsed_message, original_events = media_group_to_onebot(bot_self, media_group)
    alt_message = media_group_to_alt(media_group)
    data["tg.original_events"] = original_events
  else:
    parsed_message = message_to_onebot(bot_self, message)
    alt_message = message_to_alt(message)
  if message.chat.type in {ChatType.PRIVATE, ChatType.BOT}:
    return MessagePrivateEvent(
      id=str(uuid.uuid4()),
      time=message.date.timestamp(),
      type="message",
      detail_type="private",
      sub_type="tg.bot" if message.chat.type == ChatType.BOT else "tg.user",
      self=bot_self,
      message_id=f"{message.chat.id}:{message.id}",
      message=parsed_message,
      alt_message=alt_message,
      user_id=str(message.from_user.id) if message.from_user is not None else "",
      **data,
    )
  elif message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
    return MessageGroupEvent(
      id=str(uuid.uuid4()),
      time=message.date.timestamp(),
      type="message",
      detail_type="group",
      sub_type="tg.supergroup" if message.chat.type == ChatType.SUPERGROUP else "tg.group",
      self=bot_self,
      message_id=f"{message.chat.id}:{message.id}",
      message=parsed_message,
      alt_message=alt_message,
      user_id=str(message.from_user.id) if message.from_user is not None else "",
      group_id=str(message.chat.id),
      **data,
    )
  else:
    return MessageEvent(
      id=str(uuid.uuid4()),
      time=message.date.timestamp(),
      type="message",
      detail_type="tg.channel",
      sub_type="",
      self=bot_self,
      message_id=f"{message.chat.id}:{message.id}",
      message=parsed_message,
      alt_message=alt_message,
      **{"tg.channel_id": str(message.chat.id)},
      **data,
    )


def message_to_onebot(bot_self: BotSelf, message: MessageTG) -> MessageOB:
  result = []
  if message.reply_to_message_id is not None:
    result.append(SegmentBase.reply(
      str(message.reply_to_message_id),
      str(message.reply_to_message.from_user.id),
      {
        "tg.top_message_id": message.reply_to_top_message_id,
        "tg.message": message_event_to_onebot(bot_self, message.reply_to_message),
      }
    ))
  if message.text is not None:
    result.extend(text_to_onebot(message.text, message.entities or []))
  elif message.media is not None:
    result.extend(media_to_onebot(message))
    result.extend(text_to_onebot(
      message.poll.explanation or "",
      message.poll.explanation_entities or [],
    ) if message.poll else text_to_onebot(
      message.caption or "",
      message.caption_entities or [],
    ))
  return result


def media_group_to_onebot(
  bot_self: BotSelf,
  messages: Iterable[MessageTG],
) -> Tuple[MessageOB, List[MessageEvent]]:
  media_messages: MessageOB = []
  caption_messages: MessageOB = []
  original_events: List[MessageEvent] = []
  for message in messages:
    media_message = media_to_onebot(message)
    caption_message = text_to_onebot(message.caption or "", message.caption_entities or [])
    media_messages.extend(media_message)
    caption_messages.extend(caption_message)
    original_events.append(message_event_to_onebot(bot_self, message, None))
  return [*media_messages, *caption_messages], original_events


def text_to_onebot(text: str, entities: Iterable[MessageEntity]) -> MessageOB:
  text = str(text)  # Convert Pyrogram string to builtin string to avoid UnicodeDecodeError
  changes: List[Tuple[int, bool, MessageEntity]] = []
  for entity in entities:
    changes.append((entity.offset, True, entity))
    changes.append((entity.offset + entity.length, False, entity))
  changes.sort(key=lambda x: x[:2])
  mention: Optional[str] = None
  states = {
    "tg.sub_type": "text",
    "tg.bold": False,
    "tg.italic": False,
    "tg.strikethrough": False,
    "tg.spoiler": False,
    "tg.url": None,
    "tg.language": None,
    "tg.custom_emoji_id": None,
  }
  result: MessageOB = []
  last_pos = 0

  def append_segment() -> None:
    segment_text = text[last_pos:pos]
    if states["tg.url"] == "":
      states["tg.url"] = segment_text
    if mention is not None:
      result.append(SegmentBase.mention(mention or segment_text, states, {
        "tg.text": segment_text
      }))
    else:
      result.append(SegmentBase.text(segment_text, states))

  for pos, opening, entity in changes:
    if last_pos < pos:
      append_segment()
    last_pos = pos
    if entity.type == MessageEntityType.MENTION:
      mention = "" if opening else None
      states["tg.sub_type"] = "mention" if opening else "text"
    elif entity.type == MessageEntityType.TEXT_MENTION:
      mention = str(entity.user.id) if opening else None
      states["tg.sub_type"] = "text_mention" if opening else "text"
    elif entity.type == MessageEntityType.HASHTAG:
      states["tg.sub_type"] = "hashtag" if opening else "text"
    elif entity.type == MessageEntityType.CASHTAG:
      states["tg.sub_type"] = "cashtag" if opening else "text"
    elif entity.type == MessageEntityType.BOT_COMMAND:
      states["tg.sub_type"] = "command" if opening else "text"
    elif entity.type == MessageEntityType.URL:
      states["tg.sub_type"] = "url" if opening else "text"
      states["tg.url"] = "" if opening else None
    elif entity.type == MessageEntityType.TEXT_LINK:
      states["tg.sub_type"] = "text_link" if opening else "text"
      states["tg.url"] = entity.url if opening else None
    elif entity.type == MessageEntityType.EMAIL:
      states["tg.sub_type"] = "email" if opening else "text"
    elif entity.type == MessageEntityType.PHONE_NUMBER:
      states["tg.sub_type"] = "phone_number" if opening else "text"
    elif entity.type == MessageEntityType.BOLD:
      states["tg.bold"] = opening
    elif entity.type == MessageEntityType.ITALIC:
      states["tg.italic"] = opening
    elif entity.type == MessageEntityType.UNDERLINE:
      states["tg.underline"] = opening
    elif entity.type == MessageEntityType.STRIKETHROUGH:
      states["tg.strikethrough"] = opening
    elif entity.type == MessageEntityType.SPOILER:
      states["tg.spoiler"] = opening
    elif entity.type == MessageEntityType.CODE:
      states["tg.sub_type"] = "code" if opening else "text"
    elif entity.type == MessageEntityType.PRE:
      states["tg.sub_type"] = "pre" if opening else "text"
      states["tg.language"] = entity.language if opening else None
    elif entity.type == MessageEntityType.BLOCKQUOTE:
      states["tg.sub_type"] = "blockquote" if opening else "text"
    elif entity.type == MessageEntityType.BANK_CARD:
      states["tg.sub_type"] = "bank_card" if opening else "text"
    elif entity.type == MessageEntityType.CUSTOM_EMOJI:
      states["tg.sub_type"] = "custom_emoji" if opening else "text"
      states["tg.custom_emoji_id"] = entity.custom_emoji_id if opening else None
  pos = len(text)
  if last_pos < pos:
    append_segment()
  return result


def media_to_onebot(message: MessageTG) -> MessageOB:
  def parse_thumbs(thumbs: Optional[Iterable[Thumbnail]]) -> List[SegmentImage]:
    if not thumbs:
      return []
    return [SegmentBase.image(thumb.file_id, {
      "tg.sub_type": "thumbnail",
      "tg.unique_id": thumb.file_unique_id,
      "tg.size": thumb.file_size,
      "tg.width": thumb.width,
      "tg.height": thumb.height,
    }) for thumb in thumbs]

  def parse_audio(audio: Audio) -> SegmentAudio:
    return SegmentBase.audio(audio.file_id, {
      "tg.unique_id": audio.file_unique_id,
      "tg.name": audio.file_name,
      "tg.size": audio.file_size,
      "tg.mime": audio.mime_type,
      "tg.time": audio.date.timestamp(),
      "tg.thumbs": parse_thumbs(audio.thumbs),
      "tg.title": audio.title,
      "tg.performer": audio.performer,
      "tg.duration": audio.duration,
    })

  def parse_document(document: Document) -> SegmentFile:
    return SegmentBase.file(document.file_id, {
      "tg.unique_id": document.file_unique_id,
      "tg.name": document.file_name,
      "tg.size": document.file_size,
      "tg.mime": document.mime_type,
      "tg.time": document.date.timestamp(),
      "tg.thumbs": parse_thumbs(document.thumbs),
    })

  def parse_photo(photo: Photo) -> SegmentImage:
    return SegmentBase.image(photo.file_id, {
      "tg.sub_type": "photo",
      "tg.unique_id": photo.file_unique_id,
      "tg.size": photo.file_size,
      "tg.time": photo.date.timestamp(),
      "tg.thumbs": parse_thumbs(photo.thumbs),
      "tg.width": photo.width,
      "tg.height": photo.height,
      "tg.ttl": photo.ttl_seconds,
    })

  def parse_animation(animation: Animation) -> SegmentVideo:
    return SegmentBase.video(animation.file_id, {
      "tg.sub_type": "animation",
      "tg.unique_id": animation.file_unique_id,
      "tg.name": animation.file_name,
      "tg.size": animation.file_size,
      "tg.mime": animation.mime_type,
      "tg.time": animation.date.timestamp(),
      "tg.thumbs": parse_thumbs(animation.thumbs),
      "tg.width": animation.width,
      "tg.height": animation.height,
      "tg.duration": animation.duration,
    })

  def parse_video(video: Video) -> SegmentVideo:
    return SegmentBase.video(video.file_id, {
      "tg.sub_type": "video",
      "tg.unique_id": video.file_unique_id,
      "tg.name": video.file_name,
      "tg.size": video.file_size,
      "tg.mime": video.mime_type,
      "tg.time": video.date.timestamp(),
      "tg.thumbs": parse_thumbs(video.thumbs),
      "tg.width": video.width,
      "tg.height": video.height,
      "tg.duration": video.duration,
      "tg.supports_streaming": video.supports_streaming,
      "tg.ttl": video.ttl_seconds,
    })

  if message.media == MessageMediaType.AUDIO:
    return [parse_audio(message.audio)]
  elif message.media == MessageMediaType.DOCUMENT:
    return [parse_document(message.document)]
  elif message.media == MessageMediaType.PHOTO:
    segment = parse_photo(message.photo)
    setattr(segment, "tg.spoiler", message.has_media_spoiler)
    return [segment]
  elif message.media == MessageMediaType.STICKER:
    return [SegmentBase.image(message.sticker.file_id, {
      "tg.sub_type": "sticker",
      "tg.unique_id": message.sticker.file_unique_id,
      "tg.name": message.sticker.file_name,
      "tg.size": message.sticker.file_size,
      "tg.mime": message.sticker.mime_type,
      "tg.time": message.sticker.date.timestamp(),
      "tg.thumbs": parse_thumbs(message.sticker.thumbs),
      "tg.width": message.sticker.width,
      "tg.height": message.sticker.height,
      "tg.is_animated": message.sticker.is_animated,
      "tg.is_video": message.sticker.is_video,
      "tg.emoji": message.sticker.emoji,
      "tg.set_name": message.sticker.set_name,
    })]
  elif message.media == MessageMediaType.ANIMATION:
    segment = parse_animation(message.animation)
    setattr(segment, "tg.spoiler", message.has_media_spoiler)
    return [segment]
  elif message.media == MessageMediaType.VIDEO:
    segment = parse_video(message.video)
    setattr(segment, "tg.spoiler", message.has_media_spoiler)
    return [segment]
  elif message.media == MessageMediaType.VOICE:
    return [SegmentBase.voice(message.voice.file_id, {
      "tg.unique_id": message.voice.file_unique_id,
      "tg.size": message.voice.file_size,
      "tg.mime": message.voice.mime_type,
      "tg.time": message.voice.date.timestamp(),
      "tg.duration": message.voice.duration,
      "tg.waveform": message.voice.waveform,
    })]
  elif message.media == MessageMediaType.VIDEO_NOTE:
    return [SegmentBase.video(message.video_note.file_id, {
      "tg.sub_type": "video_note",
      "tg.unique_id": message.video_note.file_unique_id,
      "tg.size": message.video_note.file_size,
      "tg.mime": message.video_note.mime_type,
      "tg.time": message.video_note.date.timestamp(),
      "tg.thumbs": parse_thumbs(message.video_note.thumbs),
      "tg.duration": message.video_note.duration,
    })]
  elif message.media == MessageMediaType.CONTACT:
    return [SegmentBase.custom(
      "tg.contact",
      phone_number=message.contact.phone_number,
      first_name=message.contact.first_name,
      last_name=message.contact.last_name,
      user_id=message.contact.user_id,
      vcard=message.contact.vcard,
    )]
  elif message.media == MessageMediaType.LOCATION:
    return [SegmentBase.location(
      message.location.latitude,
      message.location.longitude,
      "",
      "",
      {"tg.sub_type": "location"}
    )]
  elif message.media == MessageMediaType.VENUE:
    return [SegmentBase.location(
      message.venue.location.latitude,
      message.venue.location.longitude,
      message.venue.title,
      message.venue.address,
      {
        "tg.sub_type": "venue",
        "tg.foursquare_id": message.venue.foursquare_id,
        "tg.foursquare_type": message.venue.foursquare_type
      }
    )]
  elif message.media == MessageMediaType.POLL:
    return [SegmentBase.custom(
      "tg.poll",
      id=message.poll.id,
      question=message.poll.question,
      options=[{
        "text": option.text,
        "voter_count": option.voter_count,
        "data": option.data,
      } for option in message.poll.options],
      total_voter_count=message.poll.total_voter_count,
      is_closed=message.poll.is_closed,
      is_anonymous=message.poll.is_anonymous,
      sub_type=str(message.poll.type),
      allows_multiple_answers=message.poll.allows_multiple_answers,
      chosen_option_id=message.poll.chosen_option_id,
      correct_option_id=message.poll.correct_option_id,
      open_period=message.poll.open_period,
    )]
  elif message.media == MessageMediaType.WEB_PAGE:
    if message.web_page.audio is not None:
      preview = parse_audio(message.web_page.audio)
    elif message.web_page.document is not None:
      preview = parse_document(message.web_page.document)
    elif message.web_page.photo is not None:
      preview = parse_photo(message.web_page.photo)
    elif message.web_page.animation is not None:
      preview = parse_animation(message.web_page.animation)
    elif message.web_page.video is not None:
      preview = parse_video(message.web_page.video)
    else:
      preview = None
    return [SegmentBase.custom(
      "tg.web_page",
      id=message.web_page.id,
      url=message.web_page.url,
      display_url=message.web_page.display_url,
      site_name=message.web_page.site_name,
      title=message.web_page.title,
      description=message.web_page.description,
      preview_type=message.web_page.type,
      preview=preview,
      embed_url=message.web_page.embed_url,
      embed_type=message.web_page.embed_type,
      embed_width=message.web_page.embed_width,
      embed_height=message.web_page.embed_height,
      duration=message.web_page.duration,
      author=message.web_page.author,
    )]
  elif message.media == MessageMediaType.DICE:
    return [SegmentBase.custom(
      "tg.dice",
      emoji=message.dice.emoji,
      value=message.dice.value,
    )]
  elif message.media == MessageMediaType.GAME:
    return [SegmentBase.custom(
      "tg.game",
      id=message.game.id,
      title=message.game.title,
      short_name=message.game.short_name,
      description=message.game.description,
      photo=parse_photo(message.game.photo),
      animation=(
        None
        if message.game.animation is None else
        parse_animation(message.game.animation)
      ),
    )]
  return [SegmentBase.custom("idhagn.unknown")]


def message_to_alt(message: MessageTG) -> str:
  if message.text is not None:
    return message.text
  elif message.media is not None:
    return media_to_alt(message) + (message.caption or "")
  return "[Unknown]"


def media_group_to_alt(messages: Iterable[MessageTG]) -> str:
  medias = ""
  captions = ""
  for message in messages:
    medias += media_to_alt(message)
    captions += message.caption or ""
  return medias + captions


def media_to_alt(message: MessageTG) -> str:
  TYPES = {
    MessageMediaType.AUDIO: "[Audio]",
    MessageMediaType.DOCUMENT: "[Document]",
    MessageMediaType.PHOTO: "[Photo]",
    MessageMediaType.STICKER: "[Sticker]",
    MessageMediaType.VIDEO: "[Video]",
    MessageMediaType.ANIMATION: "[Animation]",
    MessageMediaType.VOICE: "[Voice]",
    MessageMediaType.VIDEO_NOTE: "[Video Note]",
    MessageMediaType.CONTACT: "[Contact]",
    MessageMediaType.LOCATION: "[Location]",
    MessageMediaType.VENUE: "[Venue]",
    MessageMediaType.POLL: "[Poll]",
    MessageMediaType.WEB_PAGE: "[Web Page]",
    MessageMediaType.DICE: "[Dice]",
    MessageMediaType.GAME: "[Game]",
  }
  return TYPES.get(message.media, "[Unknown]")


@runtime_checkable
class HasText(Protocol):
  TEXT_LEN: ClassVar[int]
  text: str
  entities: List[MessageEntity]


@dataclasses.dataclass
class SendMessageFlags:
  disable_web_page_preview: bool = False
  disable_notification: bool = False
  protect: bool = False
  reply: Optional[DataReply] = None
  schedule: Optional[datetime] = None


@dataclasses.dataclass
class SendMessageText(HasText):
  TEXT_LEN = 4096
  text: str
  entities: List[MessageEntity]


# 图片和视频可以一起成组，其余只能和同类成组
InputMediaAlbum = Union[InputMediaPhoto, InputMediaVideo]
InputMediaGroupable = Union[InputMediaAlbum, InputMediaDocument, InputMediaAudio]


@dataclasses.dataclass
class SendMessageAlbum(HasText):
  TEXT_LEN = 1024
  media: List[InputMediaAlbum]
  text: str = dataclasses.field(default="")  # MaxLen(1024)
  entities: List[MessageEntity] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SendMessageDocument(HasText):
  TEXT_LEN = 1024
  media: List[InputMediaDocument]
  text: str = dataclasses.field(default="")  # MaxLen(1024)
  entities: List[MessageEntity] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SendMessageAudio(HasText):
  TEXT_LEN = 1024
  media: List[InputMediaAudio]
  text: str = dataclasses.field(default="")  # MaxLen(1024)
  entities: List[MessageEntity] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SendMessageVoice(HasText):
  TEXT_LEN = 1024
  file: Union[str, BinaryIO]
  text: str = dataclasses.field(default="")  # MaxLen(1024)
  entities: List[MessageEntity] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SendMessageAnimation(HasText):
  TEXT_LEN = 1024
  type: Literal["animation"]
  file: Union[str, BinaryIO]
  spoiler: bool = False
  text: str = dataclasses.field(default="")  # MaxLen(1024)
  entities: List[MessageEntity] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SendMessageSticker:
  file: Union[str, BinaryIO]


@dataclasses.dataclass
class SendMessageVideoNote:
  file: Union[str, BinaryIO]


@dataclasses.dataclass
class SendMessageLocation:
  latitude: float
  longitude: float


@dataclasses.dataclass
class SendMessageVenue:
  latitude: float
  longitude: float
  title: str
  address: str
  foursquare_id: str = ""
  foursquare_type: str = ""


@dataclasses.dataclass
class SendMessageForward:
  message_id: str
  no_media_group: bool = False


# TODO: SendMessagePoll
# TODO: SendMessageChatAction
# TODO: SendMessageContact
# TODO: SendMessageDice
# TODO: SendMessageGame


SendMessage = Union[
  SendMessageText,
  SendMessageAlbum,
  SendMessageDocument,
  SendMessageAudio,
  SendMessageVoice,
  SendMessageAnimation,
  SendMessageSticker,
  SendMessageVideoNote,
  SendMessageLocation,
  SendMessageVenue,
  SendMessageForward,
]


def message_to_telegram(message: MessageOB) -> Tuple[SendMessageFlags, List[SendMessage]]:
  # 1. 处理消息中的 Flag（Reply、Protect Content、Disable Notification 和 Scheduled）
  flags = SendMessageFlags()
  for segment in message:
    if segment.type == "reply":
      flags.reply = DataReply.parse_obj(segment.data)
    elif segment.type == "tg.protect":
      flags.protect = True
    elif segment.type == "tg.disable_web_page_preview":
      flags.disable_web_page_preview = True
    elif segment.type == "tg.disable_notification":
      flags.disable_notification = True
    elif segment.type == "tg.schedule":
      data = DataSchedule.parse_obj(segment.data)
      flags.schedule = datetime.fromtimestamp(data.time)

  # 2. 处理消息中的媒体
  def add_album(media: InputMediaAlbum) -> None:
    nonlocal last_album
    if last_album and len(last_album.media) < 10:
      last_album.media.append(media)
    else:
      last_album = SendMessageAlbum([media])
      result.append(last_album)

  def add_document(file_id: str) -> None:
    nonlocal last_document
    media = InputMediaDocument(file_id)
    if last_document and len(last_document.media) < 10:
      last_document.media.append(media)
    else:
      last_document = SendMessageDocument([media])
      result.append(last_document)

  def add_audio(file_id: str) -> None:
    nonlocal last_audio
    media = InputMediaAudio(file_id)
    if last_audio and len(last_audio.media) < 10:
      last_audio.media.append(media)
    else:
      last_audio = SendMessageAudio([media])
      result.append(last_audio)

  result: List[SendMessage] = []
  last_album: Optional[SendMessageAlbum] = None
  last_document: Optional[SendMessageDocument] = None
  last_audio: Optional[SendMessageAudio] = None
  for segment in message:
    if segment.type == "image":
      data = DataImageExt.parse_obj(segment.data)
      if data.sub_type == "photo":
        add_album(InputMediaPhoto(data.file_id, has_spoiler=data.spoiler))
      else:
        result.append(SendMessageSticker(data.file_id))
    elif segment.type == "video":
      data = DataVideoExt.parse_obj(segment.data)
      if data.sub_type == "video":
        add_album(InputMediaVideo(data.file_id, has_spoiler=data.spoiler))
      elif data.sub_type == "animation":
        result.append(SendMessageAnimation("animation", data.file_id, data.spoiler))
      else:
        result.append(SendMessageVideoNote(data.file_id))
    elif segment.type == "file":
      add_document(DataFileId.parse_obj(segment.data).file_id)
    elif segment.type == "audio":
      add_audio(DataFileId.parse_obj(segment.data).file_id)
    elif segment.type == "voice":
      result.append(SendMessageVoice(DataFileId.parse_obj(segment.data).file_id))
    elif segment.type == "location":
      data = DataLocationExt.parse_obj(segment.data)
      if data.sub_type == "venue" or (data.sub_type is None and (data.title or data.content)):
        result.append(SendMessageVenue(
          data.latitude,
          data.longitude,
          data.title,
          data.content,
          data.foursquare_id,
          data.foursquare_type,
        ))
      else:
        result.append(SendMessageLocation(data.latitude, data.longitude))
    elif segment.type == "tg.forward":
      data = DataForward.parse_obj(segment.data)
      result.append(SendMessageForward(data.message_id, data.no_media_group))

  # 3. 处理消息中的文本
  def add_entity(type: MessageEntityType, **kw: Any) -> None:
    entity = MessageEntity(type=type, offset=len(text), length=len(data.text), **kw)
    if type in last_entities:
      last_entity = last_entities[type]
      if (
        entity.offset == last_entity.offset + last_entity.length and
        entity.url == last_entity.url and
        entity.user == last_entity.user and
        entity.language == last_entity.language and
        entity.custom_emoji_id == last_entity.custom_emoji_id
      ):
        last_entity.length += entity.length
        return
    last_entities[type] = entity
    entities.append(entity)

  text = ""
  last_entities: Dict[MessageEntityType, MessageEntity] = {}
  entities: List[MessageEntity] = []
  add_space = False
  for segment in message:
    if segment.type not in {"text", "mention"}:
      continue
    if add_space:
      if text and not text[-1].isspace():
        text += " "
      add_space = False
    if segment.type == "text":
      data = DataTextExt.parse_obj(segment.data)
      if data.sub_type in {"url", "text_link"}:
        add_entity(MessageEntityType.TEXT_LINK, url=data.url)
      elif data.sub_type == "code":
        add_entity(MessageEntityType.CODE)
      elif data.sub_type == "pre":
        add_entity(MessageEntityType.PRE, language=data.language)
      elif data.sub_type == "blockquote":
        add_entity(MessageEntityType.BLOCKQUOTE)
      elif data.sub_type == "custom_emoji":
        add_entity(MessageEntityType.CUSTOM_EMOJI, custom_emoji_id=data.custom_emoji_id)
      elif data.sub_type != "text":
        add_space = True
    else:
      data = (  # parse_obj 会导致 PrivateAttr 丢失
        segment.data
        if isinstance(segment.data, DataMentionExt) else
        DataMentionExt.parse_obj(segment.data)
      )
      if data._user:  # TEXT_MENTION 不能引用不存在的用户
        data.text = data.text or (
          f"@{data._user.username}"
          if data._user.username else
          f"@{data._user.first_name} {data._user.last_name}"
          if data._user.last_name else
          f"@{data._user.first_name}"
        )
        add_entity(MessageEntityType.TEXT_MENTION, user=data._user)
      else:
        data.text = data.text or f"@{removeprefix(data.user_id, '@')}"
        add_space = True
    if data.bold:
      add_entity(MessageEntityType.BOLD)
    if data.itailc:
      add_entity(MessageEntityType.ITALIC)
    if data.strikethrough:
      add_entity(MessageEntityType.STRIKETHROUGH)
    if data.spoiler:
      add_entity(MessageEntityType.SPOILER)
    text += data.text

  # 4. 向可以添加文本的媒体添加文本、将过长的文本分片
  def slice_text(l: int) -> Tuple[str, List[MessageEntity]]:
    nonlocal text, entities
    l = min(l, len(text))
    left_text = text[:l]
    left_entities: List[MessageEntity] = []
    right_text = text[l:]
    right_entities: List[MessageEntity] = []
    for entity in entities:
      if entity.offset >= l:
        right_entities.append(entity)
        entity.offset -= l
      elif entity.offset + entity.length > l:
        right_entities.append(MessageEntity(
          type=entity.type,
          offset=0,
          length=entity.offset + entity.length - l,
          url=entity.url,
          user=entity.user,
          language=entity.language,
          custom_emoji_id=entity.custom_emoji_id,
        ))
        left_entities.append(MessageEntity(
          type=entity.type,
          offset=entity.offset,
          length=l - entity.offset,
          url=entity.url,
          user=entity.user,
          language=entity.language,
          custom_emoji_id=entity.custom_emoji_id,
        ))
      else:
        left_entities.append(entity)
    text = right_text
    entities = right_entities
    return left_text, left_entities

  for i in result:
    if isinstance(i, HasText):
      i.text, i.entities = slice_text(i.TEXT_LEN)

  while text:
    result.append(SendMessageText(*slice_text(SendMessageText.TEXT_LEN)))

  return flags, result
