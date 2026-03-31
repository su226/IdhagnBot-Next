import calendar
import re
from datetime import date, datetime, time, timedelta

DATE_ARGS_USAGE = """\
范围包含开始日期和结束日期，开始日期不填默认为今天，结束日期不填默认与开始日期相同
日期可以是以下格式
完整：2022-1-1、2022/1/1、2022年1月1日、20220101
年月：2022-1、2022/1、2022年1月、202201
月日：1-1、1/1、1月1日、0101
年份：2022、2022年
月份：1月
日期：1日
短语：今天、昨天、本周、上周、本月、上月、今年、去年"""
CHINESE_Y_RE = re.compile(r"^(\d{2}|\d{4})年?$")
CHINESE_M_RE = re.compile(r"^(\d{1,2})月$")
CHINESE_D_RE = re.compile(r"^(\d{1,2})[日号]$")
CHINESE_YM_RE = re.compile(r"^(\d{2}|\d{4})年(\d{1,2})月?$")
CHINESE_MD_RE = re.compile(r"^(\d{1,2})月(\d{1,2})[日号]??$")
CHINESE_YMD_RE = re.compile(r"^(\d{2}|\d{4})年(\d{1,2})月(\d{1,2})[日号]?$")
DASH_YM_RE = re.compile(r"^(\d{2}|\d{4})-(\d{1,2})$")
DASH_MD_RE = re.compile(r"^(\d{1,2})-(\d{1,2})$")
DASH_YMD_RE = re.compile(r"^(\d{2}|\d{4})-(\d{1,2})-(\d{1,2})$")
SLASH_YM_RE = re.compile(r"^(\d{2}|\d{4})/\d{1,2}$")
SLASH_MD_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")
SLASH_YMD_RE = re.compile(r"^(\d{2}|\d{4})/(\d{1,2})/(\d{1,2})$")


def _year(src: str) -> tuple[date, timedelta]:
  year = int(src) + date.today().year // 100 * 100 if len(src) == 2 else int(src)
  return date(year, 1, 1), timedelta(366 if calendar.isleap(year) else 365)


def _month(src: str) -> tuple[date, timedelta]:
  year = date.today().year
  month = int(src)
  _, days = calendar.monthrange(year, month)
  return date(year, month, 1), timedelta(days)


def _day(src: str) -> tuple[date, timedelta]:
  today = date.today()
  return date(today.year, today.month, int(src)), timedelta(1)


def _year_month(y_src: str, m_src: str) -> tuple[date, timedelta]:
  year = int(y_src) + date.today().year // 100 * 100 if len(y_src) == 2 else int(y_src)
  month = int(m_src)
  _, days = calendar.monthrange(year, month)
  return date(year, month, 1), timedelta(days)


def _month_day(m_src: str, d_src: str) -> tuple[date, timedelta]:
  year = date.today().year
  return date(year, int(m_src), int(d_src)), timedelta(1)


def _year_month_day(y_src: str, m_src: str, d_src: str) -> tuple[date, timedelta]:
  year = int(y_src) + date.today().year // 100 * 100 if len(y_src) == 2 else int(y_src)
  return date(year, int(m_src), int(d_src)), timedelta(1)


def parse_date(src: str) -> tuple[date, timedelta]:
  if src.isdecimal():
    if len(src) == 4:
      if int(src) < 2000:
        return _month_day(src[:2], src[2:])
      return _year(src)
    if len(src) == 6:
      return _year_month(src[:4], src[4:])
    if len(src) == 8:
      return _year_month_day(src[:4], src[4:6], src[6:])
  if match := CHINESE_Y_RE.match(src):
    return _year(match[1])
  if match := CHINESE_M_RE.match(src):
    return _month(match[1])
  if match := CHINESE_D_RE.match(src):
    return _day(match[1])
  if match := CHINESE_YM_RE.match(src):
    return _year_month(match[1], match[2])
  if match := CHINESE_MD_RE.match(src):
    return _month_day(match[1], match[2])
  if match := CHINESE_YMD_RE.match(src):
    return _year_month_day(match[1], match[2], match[3])
  if match := DASH_YM_RE.match(src):
    return _year_month(match[1], match[2])
  if match := DASH_MD_RE.match(src):
    return _month_day(match[1], match[2])
  if match := DASH_YMD_RE.match(src):
    return _year_month_day(match[1], match[2], match[3])
  if match := SLASH_YM_RE.match(src):
    return _year_month(match[1], match[2])
  if match := SLASH_MD_RE.match(src):
    return _month_day(match[1], match[2])
  if match := SLASH_YMD_RE.match(src):
    return _year_month_day(match[1], match[2], match[3])
  if src == "今天":
    return date.today(), timedelta(1)
  if src == "昨天":
    return date.today() - timedelta(1), timedelta(1)
  if src == "本周":
    today = date.today()
    weekday = calendar.weekday(today.year, today.month, today.day)
    return today - timedelta(weekday - 1), timedelta(7)
  if src == "上周":
    today = date.today()
    weekday = calendar.weekday(today.year, today.month, today.day)
    return today - timedelta(weekday + 6), timedelta(7)
  if src == "本月":
    today = date.today()
    _, days = calendar.monthrange(today.year, today.month)
    return date(today.year, today.month, 1), timedelta(days)
  if src == "上月":
    today = date.today()
    today -= timedelta(today.day)
    _, days = calendar.monthrange(today.year, today.month)
    return date(today.year, today.month, 1), timedelta(days)
  if src == "今年":
    year = date.today().year
    days = 366 if calendar.isleap(year) else 365
    return date(year, 1, 1), timedelta(days)
  if src == "去年":
    year = date.today().year - 1
    days = 366 if calendar.isleap(year) else 365
    return date(year, 1, 1), timedelta(days)
  raise ValueError(f"不是有效的日期: {src}")


def parse_date_range(start: str | None, end: str | None) -> tuple[datetime, datetime]:
  if start is None:
    start_date = end_date = date.today()
    end_len = timedelta(1)
  elif end is None:
    start_date, _ = end_date, end_len = parse_date(start)
  else:
    start_date, _ = parse_date(start)
    end_date, end_len = parse_date(end)
  start_datetime = datetime.combine(start_date, time())
  end_datetime = datetime.combine(end_date, time()) + end_len
  return start_datetime, end_datetime
