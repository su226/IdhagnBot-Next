from datetime import date

import nonebot
from pydantic import BaseModel

from idhagnbot.plugins.daily_push.module import Module, ModuleConfig

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Segment, Text, UniMessage


class Countdown(BaseModel):
  date: date
  before: str = ""
  exact: str = ""
  after: str = ""


class CountdownModuleConfig(ModuleConfig):
  countdowns: list[Countdown]

  def create_module(self) -> Module:
    return CountdownModule(self.countdowns)


class CountdownModule(Module):
  def __init__(self, countdowns: list[Countdown]) -> None:
    self.countdowns = countdowns

  async def format(self) -> list[UniMessage[Segment]]:
    lines = ["今天是："]
    today = date.today()
    for countdown in self.countdowns:
      delta = (countdown.date - today).days
      if delta > 0 and countdown.before:
        lines.append(countdown.before.format(delta))
      elif delta == 0 and countdown.exact:
        lines.append(countdown.exact)
      elif delta < 0 and countdown.after:
        lines.append(countdown.after.format(-delta))
    return [UniMessage(Text("\n".join(lines)))]
