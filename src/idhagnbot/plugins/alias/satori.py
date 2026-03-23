from nonebot.adapters import Event
from nonebot.adapters.satori import Adapter
from nonebot.adapters.satori.message import Text

from idhagnbot.plugins.alias.common import COMMAND_UPDATER_REGISTRY, CONFIG

Styles = dict[tuple[int, int], list[str]]


def filter_styles(styles: Styles, length: int) -> Styles:
  new_styles = Styles()
  for (begin, end), marks in styles.items():
    new_begin = begin - length
    new_end = end - length
    if new_end > 0:
      new_styles[(max(new_begin, 0), new_end)] = marks
  return new_styles


def update_command(scene_id: str, event: Event) -> None:
  segment = event.get_message()[0]
  if not isinstance(segment, Text):
    return
  text: str = segment.data["text"]
  original_len = len(text)
  text = text.lstrip()
  stripped_len = len(text)
  whitespace_len = original_len - stripped_len
  if alias := CONFIG().get_replacement(scene_id, text):
    alias_name_len = len(alias.name)
    segment.data["text"] = alias.definition + text[alias_name_len:]
    segment.data["styles"] = filter_styles(segment.data["styles"], whitespace_len + alias_name_len)


def register() -> None:
  COMMAND_UPDATER_REGISTRY[Adapter.get_name()] = update_command
