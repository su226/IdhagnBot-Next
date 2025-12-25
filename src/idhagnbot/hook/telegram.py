from datetime import datetime
from typing import Any

import nonebot
from nonebot.adapters import Bot
from nonebot.adapters.telegram import Adapter, Message, MessageSegment
from nonebot.adapters.telegram.message import Entity, File, UnCombinFile
from nonebot.adapters.telegram.model import MessageEntity
from pydantic_core import to_jsonable_python

from idhagnbot.hook.common import (
  CALLED_API_REGISTRY,
  CALLING_API_REGISTRY,
  SentMessage,
  call_message_send_failed_hook,
  call_message_sending_hook,
  call_message_sent_hook,
)
from idhagnbot.message import unimsg_of
from idhagnbot.url import path_from_url

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, SupportScope, Target, UniMessage
from nonebot_plugin_alconna.uniseg.segment import Media


def _normalize_entities(entities: list[MessageEntity | dict[str, Any]]) -> list[dict[str, Any]]:
  return [
    entity.model_dump(exclude_none=True) if isinstance(entity, MessageEntity) else entity
    for entity in entities
  ]


def _parse_message_from_data(
  bot: Bot,
  api: str,
  data: dict[str, Any],
) -> UniMessage[Segment] | None:
  if api == "send_message":
    if data.get("parse_mode") is not None:
      return None
    entities = Entity.from_telegram_entities(
      data["text"],
      _normalize_entities(data.get("entities") or []),
    )
    message = Message(entities)
  elif api in (
    "send_photo",
    "send_audio",
    "send_document",
    "send_video",
    "send_animation",
    "send_voice",
  ):
    if data.get("parse_mode") is not None:
      return None
    entities = Entity.from_telegram_entities(
      data.get("caption") or "",
      _normalize_entities(data.get("caption_entities") or []),
    )
    message = Message[MessageSegment](entities)
    if api == "send_photo":
      message.append(File.photo(data["photo"], data.get("has_spoiler")))
    elif api == "send_audio":
      message.append(File.audio(data["audio"], data.get("thumbnail")))
    elif api == "send_document":
      message.append(File.document(data["document"], data.get("thumbnail")))
    elif api == "send_video":
      message.append(File.video(data["video"], data.get("thumbnail"), data.get("has_spoiler")))
    elif api == "send_animation":
      message.append(
        File.animation(data["animation"], data.get("thumbnail"), data.get("has_spoiler")),
      )
    elif api == "send_voice":
      message.append(File.voice(data["voice"]))
  elif api == "send_media_group":
    medias = to_jsonable_python(data["media"], exclude_none=True)
    if medias[0].get("parse_mode") is not None:
      return None
    entities = Entity.from_telegram_entities(
      medias[0].get("caption") or "",
      medias[0].get("caption_entities") or [],
    )
    message = Message[MessageSegment](entities)
    for media in medias:
      if media["type"] == "audio":
        message.append(File.audio(media["media"], media.get("thumbnail")))
      elif media["type"] == "document":
        message.append(File.document(media["media"], media.get("thumbnail")))
      elif media["type"] == "photo":
        message.append(File.photo(media["media"], media.get("has_spoiler")))
      elif media["type"] == "video":
        message.append(
          File.video(media["media"], media.get("thumbnail"), media.get("has_spoiler")),
        )
  elif api == "send_video_note":
    message = Message(UnCombinFile.video_note(data["video_note"], data.get("thumbnail")))
  elif api == "send_location":
    message = Message(
      MessageSegment.location(
        data["latitude"],
        data["longitude"],
        data.get("horizontal_accuracy"),
        data.get("live_period"),
        data.get("heading"),
        data.get("proximity_alert_radius"),
      ),
    )
  elif api == "send_venue":
    message = Message(
      MessageSegment.venue(
        data["latitude"],
        data["longitude"],
        data["title"],
        data["address"],
        data.get("foursquare_id"),
        data.get("foursquare_type"),
        data.get("google_place_id"),
        data.get("google_place_type"),
      ),
    )
  elif api == "send_poll":
    message = Message(
      MessageSegment.poll(
        data["question"],
        [option["text"] for option in data["options"]],
        data.get("is_anonymous"),
        data.get("type"),
        data.get("allows_multiple_answers"),
        data.get("correct_option_id"),
        data.get("explanation"),
        data.get("open_period"),
        data.get("close_date"),
      ),
    )
  elif api == "send_dice":
    message = Message(MessageSegment.dice(data["emoji"]))
  elif api == "send_chat_action":
    message = Message(MessageSegment.chat_action(data["action"]))
  else:
    return None
  message = unimsg_of(message, bot)
  for segment in message[Media]:
    if isinstance(segment.id, tuple):
      segment.name, segment.raw = segment.id
      segment.id = None
    elif segment.id and segment.id.startswith("file://"):
      segment.path = path_from_url(segment.id)
      segment.id = None
  return message


def _parse_target_from_data(bot: Bot, data: dict[str, Any]) -> Target:
  chat_id = data["chat_id"]
  try:
    private = int(chat_id) > 0
  except ValueError:
    private = False
  return Target(
    chat_id,
    private=private,
    adapter=type(bot.adapter),
    self_id=bot.self_id,
    scope=SupportScope.telegram,
    extra={"message_thread_id": data.get("message_thread_id")},
  )


def _make_target(bot: Bot, chat_id: int, message_thread_id: int | None) -> Target:
  return Target(
    str(chat_id),
    private=chat_id > 0,
    adapter=type(bot.adapter),
    self_id=bot.self_id,
    scope=SupportScope.telegram,
    extra={"message_thread_id": message_thread_id},
  )


async def on_calling_api(bot: Bot, api: str, data: dict[str, Any]) -> None:
  if message := _parse_message_from_data(bot, api, data):
    target = _parse_target_from_data(bot, data)
    await call_message_sending_hook(bot, message, target)


def _message_validate(obj: dict[str, Any]) -> Message[MessageSegment]:
  return Message.model_validate(obj)


async def on_called_api(
  bot: Bot,
  e: Exception | None,
  api: str,
  data: dict[str, Any],
  result: Any,
) -> None:
  message = _parse_message_from_data(bot, api, data)
  if not message:
    return
  if e is None:
    if api in (
      "send_message",
      "forward_message",
      "send_photo",
      "send_audio",
      "send_document",
      "send_video",
      "send_animation",
      "send_voice",
      "send_video_note",
      "send_paid_media",  # not implemented in _parse_from_data
      "send_location",
      "send_venue",
      "send_contact",  # not implemented in _parse_from_data
      "send_poll",
      "send_checklist",  # not implemented in _parse_from_data
      "send_dice",
      "send_sticker",
      "send_invoice",  # not implemented in _parse_from_data
      "send_game",  # not implemented in _parse_from_data
    ):
      messages = [
        SentMessage(
          datetime.fromtimestamp(result["date"]),
          str(result["message_id"]),
          unimsg_of(_message_validate(result), bot),
        ),
      ]
      chat_id = result["chat"]["id"]
      message_thread_id = result.get("message_thread_id")
      target = _make_target(bot, chat_id, message_thread_id)
    elif api == "send_media_group":
      messages = [
        SentMessage(
          datetime.fromtimestamp(message["date"]),
          str(message["message_id"]),
          unimsg_of(_message_validate(message), bot),
        )
        for message in result
      ]
      chat_id = result[0]["chat"]["id"]
      message_thread_id = result[0].get("message_thread_id")
      target = _make_target(bot, chat_id, message_thread_id)
    elif api == "send_chat_action":
      messages = [
        SentMessage(
          datetime.now(),
          None,
          unimsg_of(Message(MessageSegment.chat_action(data["action"])), bot),
        ),
      ]
      target = _parse_target_from_data(bot, data)
    else:
      return
    await call_message_sent_hook(bot, message, messages, target)
  else:
    target = _parse_target_from_data(bot, data)
    await call_message_send_failed_hook(bot, message, target, e)


def register() -> None:
  CALLING_API_REGISTRY[Adapter.get_name()] = on_calling_api
  CALLED_API_REGISTRY[Adapter.get_name()] = on_called_api
