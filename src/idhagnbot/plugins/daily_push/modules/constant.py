from typing import override

from arclet.entari import MessageChain

from idhagnbot.plugins.daily_push.module import SimpleModule


class ConstantModule(SimpleModule):
    type = "constant"
    message: str

    @override
    async def format(self) -> list[MessageChain]:
        return [MessageChain.of(self.message)]
