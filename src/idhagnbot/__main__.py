import nonebot
import importlib
import idhagnbot

ADAPTERS = [
  "nonebot.adapters.telegram",
  "nonebot.adapters.onebot.v11",
]

nonebot.init()
driver = nonebot.get_driver()

for adapter in ADAPTERS:
  try:
    driver.register_adapter(importlib.import_module(adapter).Adapter)
  except ImportError:
    pass

idhagnbot.load_plugins()
nonebot.run()
