import os
import stat
from collections.abc import AsyncGenerator
from typing import Any, Literal

import nonebot
from anyio import Path
from anyio.to_thread import run_sync
from nonebot.config import Config as NonebotConfig
from nonebot.drivers import ASGIMixin, HTTPServerSetup, Request, Response
from pydantic import BaseModel, ValidationError
from yarl import URL

from idhagnbot.config import Reloadable, SharedConfig
from idhagnbot.webui.common import ResponseData, authenticate

nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_config_dir

CONFIG_DIR = Path(get_config_dir(None))


class Config(BaseModel):
  path: str
  type: Literal["shared", "dotenv", "other"]
  description: str = ""
  exist: bool


class ConfigsResponseData(BaseModel):
  configs: list[Config]


async def walk(top: os.PathLike[str]) -> AsyncGenerator[tuple[str, list[str], list[str]]]:
  it = await run_sync(os.walk, top)

  def _gen() -> tuple[str, list[str], list[str]] | None:
    try:
      return next(it)
    except StopIteration:
      return None

  while True:
    value = await run_sync(_gen)
    if value is None:
      break
    yield value


async def handle_configs(request: Request) -> Response:
  if response := authenticate(request):
    return response
  configs = dict[str, Config]()
  for config in SharedConfig.all.values():
    path = CONFIG_DIR / "idhagnbot" / f"{config.name}.yaml"
    path_str = str("config" / path.relative_to(CONFIG_DIR))
    configs[path_str] = Config(
      path=path_str,
      type="shared",
      description=config.model.__doc__ or "",
      exist=await path.is_file(),
    )
  async for root, _, files in walk(CONFIG_DIR):
    path_root = Path(root).relative_to(CONFIG_DIR)
    for file in files:
      path_str = str("config" / path_root / file)
      if path_str not in configs:
        configs[path_str] = Config(path=path_str, type="other", exist=True)
  has_default = False
  has_dev = False
  has_prod = False
  cwd = await Path.cwd()
  async for child in cwd.iterdir():
    if (child.name == ".env" or child.name.startswith(".env.")) and await child.is_file():
      if child.name == ".env":
        has_default = True
      if child.name == ".env.dev":
        has_dev = True
      if child.name == ".env.prod":
        has_prod = True
      configs[child.name] = Config(path=child.name, type="dotenv", exist=True)
  if not has_default:
    configs[".env"] = Config(path=".env", type="dotenv", exist=False)
  if not has_dev:
    configs[".env.dev"] = Config(path=".env.dev", type="dotenv", exist=False)
  if not has_prod:
    configs[".env.prod"] = Config(path=".env.prod", type="dotenv", exist=False)
  return ResponseData.res_success(ConfigsResponseData(configs=list(configs.values())))


class ConfigGetResponseData(BaseModel):
  config: str
  schema: Any


async def handle_config_get(request: Request) -> Response:
  if response := authenticate(request):
    return response
  name = request.url.query.get("name", "")
  schema = {}
  if name.startswith("config/"):
    path = Path(await run_sync(os.path.abspath, CONFIG_DIR / name[7:]))
    if not path.is_relative_to(CONFIG_DIR) or path == CONFIG_DIR:
      return ResponseData.res_error(400, "无效配置名")
    rel = path.relative_to(CONFIG_DIR)
    if (
      len(rel.parts) == 2
      and rel.parts[0] == "idhagnbot"
      and rel.suffix == ".yaml"
      and (config := SharedConfig.all.get(rel.stem))
    ):
      schema = config.model.model_json_schema()
  else:
    path = await Path(name).resolve()
    cwd = await Path.cwd()
    if not (path.name == ".env" or path.name.startswith(".env.")) or path.parent != cwd:
      return ResponseData.res_error(400, "无效配置名")
    schema = NonebotConfig.model_json_schema()
  try:
    st = await path.stat()
  except FileNotFoundError:
    st = None
  if st is not None and not stat.S_ISREG(st.st_mode):
    return ResponseData.res_error(400, "不是文件")
  if st is None:
    content = ""
  else:
    async with await path.open("r", errors="replace") as file:
      content = await file.read()
  return ResponseData.res_success(ConfigGetResponseData(config=content, schema=schema))


class ConfigSetRequestData(BaseModel):
  config: str


class ConfigSetDeleteResponseData(BaseModel):
  reloaded: bool


async def handle_config_set(request: Request) -> Response:
  if response := authenticate(request):
    return response
  try:
    data = ConfigSetRequestData.model_validate(request.json)
  except ValidationError as e:
    return ResponseData.res_error(400, str(e))
  name = request.url.query.get("name", "")
  config = None
  if name.startswith("config/"):
    path = Path(await run_sync(os.path.abspath, CONFIG_DIR / name[7:]))
    if not path.is_relative_to(CONFIG_DIR) or path == CONFIG_DIR:
      return ResponseData.res_error(400, "无效配置名")
    rel = path.relative_to(CONFIG_DIR)
    if len(rel.parts) == 2 and rel.parts[0] == "idhagnbot" and rel.suffix == ".yaml":
      config = SharedConfig.all.get(rel.stem)
  else:
    path = await Path(name).resolve()
    cwd = await Path.cwd()
    if not (path.name == ".env" or path.name.startswith(".env.")) or path.parent != cwd:
      return ResponseData.res_error(400, "无效配置名")
  async with await path.open("w") as f:
    await f.write(data.config)
  reloaded = False
  if config and config.reloadable is not Reloadable.FALSE:
    reloaded = True
    config.reload()
  return ResponseData.res_success(ConfigSetDeleteResponseData(reloaded=reloaded))


async def handle_config_delete(request: Request) -> Response:
  if response := authenticate(request):
    return response
  name = request.url.query.get("name", "")
  config = None
  if name.startswith("config/"):
    path = Path(await run_sync(os.path.abspath, CONFIG_DIR / name[7:]))
    if not path.is_relative_to(CONFIG_DIR) or path == CONFIG_DIR:
      return ResponseData.res_error(400, "无效配置名")
    rel = path.relative_to(CONFIG_DIR)
    if len(rel.parts) == 2 and rel.parts[0] == "idhagnbot" and rel.suffix == ".yaml":
      config = SharedConfig.all.get(rel.stem)
  else:
    path = await Path(name).resolve()
    cwd = await Path.cwd()
    if not (path.name == ".env" or path.name.startswith(".env.")) or path.parent != cwd:
      return ResponseData.res_error(400, "无效配置名")
  await path.unlink(missing_ok=True)
  reloaded = False
  if config and config.reloadable is not Reloadable.FALSE:
    reloaded = True
    config.reload()
  return ResponseData.res_success(ConfigSetDeleteResponseData(reloaded=reloaded))


def setup(driver: ASGIMixin) -> None:
  driver.setup_http_server(
    HTTPServerSetup(
      URL("/idhagnbot-api/configs"),
      "GET",
      "IdhagnBot Config Editor List Configs",
      handle_configs,
    ),
  )
  driver.setup_http_server(
    HTTPServerSetup(
      URL("/idhagnbot-api/config"),
      "GET",
      "IdhagnBot Config Editor Get Config",
      handle_config_get,
    ),
  )
  driver.setup_http_server(
    HTTPServerSetup(
      URL("/idhagnbot-api/config"),
      "POST",
      "IdhagnBot Config Editor Set Config",
      handle_config_set,
    ),
  )
  driver.setup_http_server(
    HTTPServerSetup(
      URL("/idhagnbot-api/config"),
      "DELETE",
      "IdhagnBot Config Editor Delete Config",
      handle_config_delete,
    ),
  )
