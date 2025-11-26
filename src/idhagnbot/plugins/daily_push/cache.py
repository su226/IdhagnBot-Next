from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import anyio
import nonebot

nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_cache_dir

BASE_DIR = get_cache_dir("idhagnbot") / "daily_push"
DEFAULT_UPDATE_TIME = time(tzinfo=ZoneInfo("Asia/Shanghai"))


class BaseCache:
  def __init__(
    self,
    filename: str,
    enable_prev: bool = False,
    extra_files: list[str] | None = None,
  ) -> None:
    self.lock = anyio.Lock()
    self.path = BASE_DIR / filename
    self.date_path = self.path.with_suffix(".date")
    self.enable_prev = enable_prev
    self.extra_files = extra_files or []

  def get_update_date(self) -> tuple[datetime, datetime]:
    raise NotImplementedError

  def check(self) -> bool:
    if not (self.path.exists() and self.date_path.exists()):
      return False
    with self.date_path.open() as f:
      update_date = datetime.fromisoformat(f.read())
    prev_update_date, next_update_date = self.get_update_date()
    return prev_update_date <= update_date < next_update_date

  def move_prev(self, path: Path) -> None:
    path.rename(path.with_suffix(".prev" + path.suffix))

  def write_date(self) -> None:
    with self.date_path.open("w") as f:
      f.write(datetime.now(timezone.utc).astimezone().isoformat())

  async def update(self) -> None:
    self.path.parent.mkdir(parents=True, exist_ok=True)
    if self.enable_prev and self.path.exists() and self.date_path.exists():
      with self.date_path.open() as f:
        update_date = datetime.fromisoformat(f.read())
      prev_update_date, _ = self.get_update_date()
      if update_date < prev_update_date:
        self.move_prev(self.path)
        self.move_prev(self.date_path)
        for file in self.extra_files:
          self.move_prev(self.path.with_name(file))
    await self.do_update()
    self.write_date()

  async def do_update(self) -> None:
    raise NotImplementedError

  async def ensure(self) -> None:
    if not self.check():
      async with self.lock:
        if not self.check():
          await self.update()


class DailyCache(BaseCache):
  def __init__(
    self,
    filename: str,
    enable_prev: bool = False,
    extra_files: list[str] | None = None,
    update_time: time = DEFAULT_UPDATE_TIME,
  ) -> None:
    super().__init__(filename, enable_prev, extra_files)
    self.update_time = update_time

  def get_update_date(self) -> tuple[datetime, datetime]:
    now = datetime.now(self.update_time.tzinfo)
    update = datetime.combine(now, self.update_time)
    if update > now:
      return update - timedelta(1), update
    return update, update + timedelta(1)


class WeeklyCache(BaseCache):
  def __init__(
    self,
    filename: str,
    enable_prev: bool = False,
    extra_files: list[str] | None = None,
    update_weekday: int = 0,
    update_time: time = DEFAULT_UPDATE_TIME,
  ) -> None:
    super().__init__(filename, enable_prev, extra_files)
    self.update_weekday = update_weekday
    self.update_time = update_time

  def get_update_date(self) -> tuple[datetime, datetime]:
    now = datetime.now(self.update_time.tzinfo)
    update = datetime.combine(now, self.update_time)
    update += timedelta(self.update_weekday - update.weekday())
    if update > now:
      return update - timedelta(7), update
    return update, update + timedelta(7)
