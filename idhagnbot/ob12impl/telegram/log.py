import re

from pyrogram.types import Chat, ChatPreview, User
from pyrogram.enums import ChatType


def escape_log(s: str) -> str:
  return re.sub(r"</?((?:[fb]g\s)?[^<>\s]*)>", r"\\\g<0>", s)


def log_user(user: User) -> str:
  name = user.first_name
  if user.last_name is not None:
    name += f" {user.last_name}"
  id = str(user.id)
  if user.username is not None:
    id += f"/@{escape_log(user.username)}"
  type = "bot" if user.is_bot else "user"
  return f"{type} <cyan>{escape_log(name)}[{id}]</cyan>"


def log_chat(chat: Chat) -> str:
  types = {
    ChatType.PRIVATE: "user",
    ChatType.BOT: "bot",
    ChatType.GROUP: "group",
    ChatType.SUPERGROUP: "supergroup",
    ChatType.CHANNEL: "channel",
  }
  return f"{types[chat.type]} <blue>{escape_log(chat.title)}[{chat.id}]</blue>"


def log_chat_preview(chat: ChatPreview, id: str) -> str:
  return f"{chat.type} <blue>{escape_log(chat.title)}[{id}]</blue>"
