import importlib
import pkgutil

for module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"idhagnbot.plugins.{module.name}")
