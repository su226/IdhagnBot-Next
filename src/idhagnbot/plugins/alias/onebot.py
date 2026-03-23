from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Adapter, MessageEvent

from idhagnbot.plugins.alias.common import COMMAND_UPDATER_REGISTRY, CONFIG


def update_command(scene_id: str, event: Event) -> None:
  assert isinstance(event, MessageEvent)
  segment = event.message[0]
  if not segment.is_text():
    return
  text: str = segment.data["text"]
  text = text.lstrip()
  if alias := CONFIG().get_replacement(scene_id, text):
    segment.data["text"] = alias.definition + text[len(alias.name) :]


def register() -> None:
  COMMAND_UPDATER_REGISTRY[Adapter.get_name()] = update_command
