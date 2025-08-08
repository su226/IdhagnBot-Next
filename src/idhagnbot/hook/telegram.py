from itertools import chain
from typing import Any, Optional, cast

import nonebot
from nonebot.adapters import Bot
from nonebot.adapters.telegram import Adapter, Message, MessageSegment
from nonebot.adapters.telegram.message import Entity, File, UnCombinFile

from idhagnbot.hook.common import (
  CALLED_API_REGISTRY,
  CALLING_API_REGISTRY,
  call_message_send_failed_hook,
  call_message_sending_hook,
  call_message_sent_hook,
)

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, SupportScope, Target, UniMessage


def _parse_from_data(
  bot: Bot,
  api: str,
  data: dict[str, Any],
) -> Optional[tuple[UniMessage[Segment], Target]]:
  if api == "send_message":
    if data.get("parse_mode") is not None:
      return None
    entities = Entity.from_telegram_entities(data["text"], data.get("entities") or [])
    message = UniMessage.of(Message(entities))
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
      data.get("caption_entities") or [],
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
    message = UniMessage.of(message)
  elif api == "send_media_group":
    media = data["media"][0]
    if media.get("parse_mode") is not None:
      return None
    entities = Entity.from_telegram_entities(
      media.get("caption") or "",
      media.get("caption_entities") or [],
    )
    message = Message[MessageSegment](entities)
    for media in data["media"]:
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
    message = UniMessage.of(message)
  elif api == "send_video_note":
    message = UniMessage.of(
      Message(UnCombinFile.video_note(data["video_note"], data.get("thumbnail"))),
    )
  elif api == "send_location":
    message = UniMessage.of(
      Message(
        MessageSegment.location(
          data["latitude"],
          data["longitude"],
          data.get("horizontal_accuracy"),
          data.get("live_period"),
          data.get("heading"),
          data.get("proximity_alert_radius"),
        ),
      ),
    )
  elif api == "send_venue":
    message = UniMessage.of(
      Message(
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
      ),
    )
  elif api == "send_poll":
    message = UniMessage.of(
      Message(
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
      ),
    )
  elif api == "send_dice":
    message = UniMessage.of(Message(MessageSegment.dice(data["emoji"])))
  elif api == "send_chat_action":
    message = UniMessage.of(Message(MessageSegment.chat_action(data["action"])))
  else:
    return None
  chat_id = data["chat_id"]
  try:
    private = int(chat_id) > 0
  except ValueError:
    private = False
  target = Target(
    chat_id,
    private=private,
    adapter=type(bot.adapter),
    self_id=bot.self_id,
    scope=SupportScope.telegram,
    extra={"message_thread_id": data.get("message_thread_id")},
  )
  return message, target


async def on_calling_api(bot: Bot, api: str, data: dict[str, Any]) -> None:
  if parsed := _parse_from_data(bot, api, data):
    message, target = parsed
    await call_message_sending_hook(bot, message, target)


async def on_called_api(
  bot: Bot,
  e: Optional[Exception],
  api: str,
  data: dict[str, Any],
  result: Any,
) -> None:
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
      message = UniMessage.of(Message.model_validate(result))
      chat_id = result["chat"]["id"]
      message_thread_id = result.get("message_thread_id")
      message_ids = [str(result["message_id"])]
    elif api == "send_media_group":
      message = UniMessage.of(
        Message(
          chain.from_iterable(
            cast(Message[MessageSegment], Message.model_validate(message)) for message in result
          ),
        ),
      )
      chat_id = result[0]["chat"]["id"]
      message_thread_id = result[0].get("message_thread_id")
      message_ids = [str(message["message_id"]) for message in result]
    elif api == "send_chat_action":
      message = UniMessage.of(Message(MessageSegment.chat_action(data["action"])))
      chat_id = data["chat_id"]
      message_thread_id = data.get("message_thread_id")
      message_ids = []
    else:
      return
    target = Target(
      chat_id,
      private=chat_id > 0,
      adapter=type(bot.adapter),
      self_id=bot.self_id,
      scope=SupportScope.telegram,
      extra={"message_thread_id": message_thread_id},
    )
    await call_message_sent_hook(bot, message, target, message_ids)
  elif parsed := _parse_from_data(bot, api, data):
    message, target = parsed
    await call_message_send_failed_hook(bot, message, target, e)


def register() -> None:
  CALLING_API_REGISTRY[Adapter.get_name()] = on_calling_api
  CALLED_API_REGISTRY[Adapter.get_name()] = on_called_api
