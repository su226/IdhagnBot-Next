import asyncio
import os
import random
from datetime import datetime
from importlib.metadata import version
from typing import Awaitable, Dict, List, Optional, Tuple, TypeVar, cast
from urllib.parse import urlparse

from loguru import logger
from pydantic import Field, ValidationError
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import RPCError
from pyrogram.raw.functions.ping import Ping
from pyrogram.types import ChatPreview, Message as MessageTG, User

from idhagnbot.ob12impl.telegram.log import escape_log, log_chat, log_chat_preview, log_user
from idhagnbot.ob12impl.telegram.message import (
  DataMentionExt, InputMediaGroupable, SendMessageAlbum, SendMessageAnimation, SendMessageAudio,
  SendMessageDocument, SendMessageForward, SendMessageLocation, SendMessageSticker,
  SendMessageText, SendMessageVenue, SendMessageVideoNote, SendMessageVoice,
  message_event_to_onebot, message_to_telegram, removeprefix
)
from idhagnbot.obc.v12.action import (
  DeleteMessageParam, DeleteMessageResult, SendMessageParam, SendMessageResult
)
from idhagnbot.obc.v12.app import ActionResult, ActionResultTuple, App as BaseApp
from idhagnbot.obc.v12.event import BotSelf, BotStatus, MessageEvent, Status, Version
from idhagnbot.obc.v12.message import Message as MessageOB


class DeleteMessageParamExt(DeleteMessageParam):
  no_media_group: bool = Field(False, alias="tg.no_media_group")


T = TypeVar("T")


class App(BaseApp):
  def __init__(
    self,
    api_id: int,
    api_hash: str,
    bot_token: str,
    proxy: Optional[str] = None,
  ) -> None:
    super().__init__()
    client_args = {}
    if proxy:
      parsed_proxy = urlparse(proxy)
      client_args["proxy"] = {
        "scheme": parsed_proxy.scheme,
        "hostname": parsed_proxy.hostname,
        "port": parsed_proxy.port,
        "username": parsed_proxy.username,
        "password": parsed_proxy.password,
      }
    self.id, _ = bot_token.split(":", 1)
    workdir = os.path.join(os.getcwd(), "data")
    os.makedirs(workdir, exist_ok=True)
    self.tg = Client(
      f"bot_{self.id}",
      api_id,
      api_hash,
      bot_token=bot_token,
      parse_mode=ParseMode.DISABLED,
      workdir=workdir,
      **client_args,
    )
    self.tg.on_message(not filters.service)(self.on_message)
    self.__media_groups: Dict[str, List[MessageTG]] = {}
    self.add_action(self.send_message)
    self.add_action(self.delete_message)

  def get_self(self) -> BotSelf:
    return BotSelf(platform="telegram", user_id=self.id)

  async def get_version(self) -> Version:
    return Version(impl="idhagnbot-telegram", version=version("idhagnbot"), onebot_version="12")

  async def get_status(self) -> Status:
    try:
      await self.tg.invoke(Ping(ping_id=random.randrange(1 << 63)))
      good = True
    except RPCError:
      good = False
    return Status(good=good, bots=[BotStatus(self=self.get_self(), online=good)])

  async def setup(self) -> None:
    await super().setup()
    logger.info(f"Connecting bot {self.id} to Telegram.")
    await self.tg.start()

  async def shutdown(self) -> None:
    await super().shutdown()
    await self.tg.stop()

  async def _guard(self, coro: Awaitable[T]) -> T:
    try:
      return await coro
    except OSError as e:
      raise ActionResult(33000, str(e), None) from e
    except ValueError as e:
      raise ActionResult(35001, str(e), None) from e
    except RPCError as e:
      if e.CODE == 400:
        code = 35000
      else:
        code = 34000 + cast(int, e.CODE)
      raise ActionResult(code, removeprefix(str(e), "Telegram says: "), None) from e

  async def _log_chat(self, chat_id: str) -> str:
    try:
      chat = await self.tg.resolve_peer(chat_id)
      if id := getattr(chat, "chat_id", None):
        chat = await self.tg.get_chat(id)
        if isinstance(chat, ChatPreview):
          return log_chat_preview(chat, id)
        return log_chat(chat)
      elif id := getattr(chat, "user_id"):
        return log_user(cast(User, await self.tg.get_users(id)))
    except RPCError:
      pass
    return f"<red>{escape_log(repr(chat_id))}</red>"

  async def send_message(
    self,
    params: SendMessageParam,
    _bot_self: Optional[BotSelf],
  ) -> ActionResultTuple[SendMessageResult]:
    if params.detail_type == "private":
      chat_id = params.user_id
    elif params.detail_type == "group":
      chat_id = params.group_id
    else:
      return 10004, f"Send message of type {params.detail_type} is unsupported.", None

    try:
      flags, messages = message_to_telegram(await self.resolve_send_message(params.message))
    except ValidationError as e:
      return 10003, f"Failed to parse message: {e}", None

    # Pyrogram 类型标注没有 Optional
    schedule_date = cast(datetime, flags.schedule)
    reply_to_message_id = cast(int, None)
    if flags.reply:
      parts = flags.reply.message_id.split(":", 2)
      if len(parts) == 1:
        reply_to_message_id = parts[0]
      elif len(parts) == 2:
        reply_to_chat_id, reply_to_message_id = parts
        if await self.tg.resolve_peer(chat_id) != await self.tg.resolve_peer(reply_to_chat_id):
          msg = f"Can only reply to message in same chat: {flags.reply}"
          return 10006, msg, None
      else:
        return 10006, f"Bad reply message_id: {flags.reply}", None
      try:
        reply_to_message_id = int(reply_to_message_id)
      except ValueError:
        return 10006, f"Bad reply message_id: {flags.reply}", None

    results: List[MessageTG] = []
    chat = await self._log_chat(chat_id)
    for message in messages:
      try:
        if isinstance(message, SendMessageText):
          results.append(await self._guard(self.tg.send_message(
            chat_id,
            message.text,
            entities=message.entities,
            disable_web_page_preview=flags.disable_web_page_preview,
            disable_notification=flags.disable_notification,
            reply_to_message_id=reply_to_message_id,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          )))
        elif isinstance(message, (SendMessageAlbum, SendMessageDocument, SendMessageAudio)):
          message.media[0].caption = message.text
          message.media[0].caption_entities = message.entities
          results.extend(await self._guard(self.tg.send_media_group(
            chat_id,
            cast(List[InputMediaGroupable], message.media),
            disable_notification=flags.disable_notification,
            reply_to_message_id=reply_to_message_id,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          )))
        elif isinstance(message, SendMessageVoice):
          results.append(cast(MessageTG, await self._guard(self.tg.send_voice(
            chat_id,
            message.file,
            message.text,
            caption_entities=message.entities,
            disable_notification=flags.disable_notification,
            reply_to_message_id=reply_to_message_id,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          ))))
        elif isinstance(message, SendMessageAnimation):
          results.append(cast(MessageTG, await self._guard(self.tg.send_animation(
            chat_id,
            message.file,
            message.text,
            caption_entities=message.entities,
            disable_notification=flags.disable_notification,
            reply_to_message_id=reply_to_message_id,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          ))))
        elif isinstance(message, SendMessageSticker):
          results.append(cast(MessageTG, await self._guard(self.tg.send_sticker(
            chat_id,
            message.file,
            disable_notification=flags.disable_notification,
            reply_to_message_id=reply_to_message_id,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          ))))
        elif isinstance(message, SendMessageVideoNote):
          results.append(cast(MessageTG, await self._guard(self.tg.send_video_note(
            chat_id,
            message.file,
            disable_notification=flags.disable_notification,
            reply_to_message_id=reply_to_message_id,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          ))))
        elif isinstance(message, SendMessageLocation):
          results.append(await self._guard(self.tg.send_location(
            chat_id,
            message.latitude,
            message.longitude,
            disable_notification=flags.disable_notification,
            reply_to_message_id=reply_to_message_id,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          )))
        elif isinstance(message, SendMessageVenue):
          results.append(await self._guard(self.tg.send_venue(
            chat_id,
            message.latitude,
            message.longitude,
            message.title,
            message.address,
            message.foursquare_id,
            message.foursquare_type,
            disable_notification=flags.disable_notification,
            reply_to_message_id=reply_to_message_id,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          )))
        elif isinstance(message, SendMessageForward):
          forward_chat_id, forward_message_id = await self._try_get_message_ids(
            message.message_id,
            message.no_media_group,
          )
          results.extend(cast(List[MessageTG], await self.tg.forward_messages(
            chat_id,
            forward_chat_id,
            forward_message_id,
            disable_notification=flags.disable_notification,
            schedule_date=schedule_date,
            protect_content=flags.protect,
          )))
        logger.opt(colors=True).success(f"Message sent to {chat}: {escape_log(repr(message))}")
      except ActionResult as e:
        logger.opt(colors=True).error(
          f"Send message to {chat} failed: {escape_log(repr(message))}"
        )
        logger.error(e.message)
        raise
    return 0, "", SendMessageResult(
      message_id=f"{results[0].chat.id}:{results[0].id}",
      time=results[0].date.timestamp(),
      **{"tg.events": [message_event_to_onebot(self.get_self(), event) for event in results]}
    )

  async def delete_message(
    self,
    params: DeleteMessageParamExt,
    _bot_self: Optional[BotSelf],
  ) -> ActionResultTuple[DeleteMessageResult]:
    chat_id, message_ids = await self._try_get_message_ids(
      params.message_id,
      params.no_media_group,
    )
    message_id_str = ", ".join(map(str, message_ids))
    chat = await self._log_chat(chat_id)
    try:
      await self._guard(self.tg.delete_messages(chat_id, message_ids))
      logger.opt(colors=True).success(f"Message <cyan>{message_id_str}</cyan> in {chat} deleted.")
    except ActionResult as e:
      logger.opt(colors=True).error(
        f"Delete message <cyan>{message_id_str}</cyan> in {chat} failed."
      )
      logger.error(e.message)
      raise
    return 0, "", None

  async def _try_get_message_ids(
    self,
    message_id: str,
    no_media_group: bool = False,
  ) -> Tuple[str, List[int]]:
    async def do_get_media_group():
      try:
        return [message.id for message in await self.tg.get_media_group(chat_id, message_id_int)]
      except ValueError:
        return [message_id_int]

    parts = message_id.split(":", 2)
    if len(parts) != 2:
      raise ActionResult(10003, f"Invalid message ID: {message_id!r}", None)
    chat_id, message_id = parts
    try:
      message_id_int = int(message_id)
    except ValueError as e:
      raise ActionResult(10003, f"Invalid message ID: {message_id!r}", None) from e
    if not no_media_group:
      return chat_id, await self._guard(do_get_media_group())
    return chat_id, [message_id_int]

  async def on_message(self, tg: Client, message: MessageTG) -> None:
    try:
      if message.media_group_id is not None:
        if message.media_group_id in self.__media_groups:
          self.__media_groups[message.media_group_id].append(message)
          return
        media_group = self.__media_groups[message.media_group_id] = [message]
        await asyncio.sleep(0.1)
        del self.__media_groups[message.media_group_id]
        media_group.sort(key=lambda x: x.id)
      else:
        media_group = None
      parsed_event = message_event_to_onebot(self.get_self(), message, media_group)
      await self.resolve_recv_message(parsed_event)
    except Exception:
      logger.exception(f"Failed to parse Telegram message: {message}")
      return
    if message.chat.type in {ChatType.PRIVATE, ChatType.BOT}:
      chat_name = log_user(message.from_user)
    elif message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
      chat_name = f"{log_chat(message.chat)} {log_user(message.from_user)}"
    else:
      chat_name = log_chat(message.chat)
    if media_group:
      ids = ", ".join(map(str, media_group))
    else:
      ids = str(message.id)
    logger.opt(colors=True).info(
      f"Message <cyan>{ids}</cyan> from {chat_name}: " +
      escape_log(repr(parsed_event.alt_message))
    )
    self.emit(parsed_event)

  async def resolve_recv_message(self, event: MessageEvent) -> None:
    async def resolve_mention(id: str) -> None:
      try:
        mentions[id] = cast(User, await self.tg.get_users(id))
      except RPCError:
        pass

    mentions: Dict[str, Optional[User]] = {}
    events = [event, *(event["tg.original_events"] or [])]

    for event in events:
      for segment in event.message:
        if segment.type == "mention":
          mentions[segment.data.user_id] = None
    await asyncio.gather(*[resolve_mention(id) for id in mentions])

    for event in events:
      for segment in event.message:
        if segment.type == "mention" and (user := mentions[segment.data.user_id]):
          segment.data.user_id = str(user.id)

  async def resolve_send_message(self, message: MessageOB) -> MessageOB:
    async def resolve_mention(id: str) -> None:
      try:
        mentions[id] = cast(User, await self.tg.get_users(id))
      except RPCError:
        logger.warning(f"Invalid mention to user {id!r}")

    mentions: Dict[str, Optional[User]] = {}

    for segment in message:
      if segment.type == "mention":
        segment.data.user_id = removeprefix(segment.data.user_id, "@")
        mentions[segment.data.user_id] = None
    await asyncio.gather(*[resolve_mention(id) for id in mentions])

    result: MessageOB = []
    for segment in message:
      if segment.type == "mention":
        segment.data = DataMentionExt.parse_obj(segment.data)
        if (user := mentions[segment.data.user_id]):
          segment.data._user = user
      result.append(segment)
    return result
