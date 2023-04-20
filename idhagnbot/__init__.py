import nonebot
from nonebot.adapters.onebot.v12 import Adapter


def main() -> None:
  nonebot.init()
  nonebot.get_driver().register_adapter(Adapter)
  nonebot.load_plugins("idhagnbot/plugins")
  nonebot.run()
