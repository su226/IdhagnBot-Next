from datetime import date
from typing import override

from arclet.entari import MessageChain, Text
from pydantic import BaseModel

from idhagnbot.plugins.daily_push.module import SimpleModule


class Countdown(BaseModel):
    date: date
    before: str = ""
    exact: str = ""
    after: str = ""


class CountdownModule(SimpleModule):
    type = "countdown"
    countdowns: list[Countdown]

    @override
    async def format(self) -> list[MessageChain]:
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
        return [MessageChain(Text("\n".join(lines)))]
