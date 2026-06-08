import re
import warnings
from contextlib import AsyncExitStack
from contextvars import ContextVar
from enum import Enum
from pathlib import Path
from typing import Annotated, Protocol

import nonebot.message
from nonebot.adapters import Bot, Event
from nonebot.matcher import Matcher, current_matcher
from nonebot.params import Depends
from nonebot.typing import T_DependencyCache, T_State
from tarina.lang import lang

__all__ = [
  "LOCALE_KEY",
  "L",
  "Locale",
  "bound_lang",
  "get_current_locale",
  "get_fallback",
  "get_full_name",
  "get_name",
  "lang",
]
LOCALE_KEY = "_idhagnbot_locale"
lang.load(Path(__file__).parent)
_current_locale = ContextVar[str | None]("_current_locale")
_I18N_PATTERN = re.compile(r"__([a-z0-9_]+):([a-z0-9_\.]+)__")


def _raw_require(
  scope: str,
  type: str,  # noqa: A002
  locale: str,
) -> str:
  return lang._LangConfig__langs[locale][scope][type]  # ty:ignore[unresolved-attribute]


def get_name(locale: str) -> str | None:
  try:
    return _raw_require("idhagnbot", "lang_name", locale)
  except KeyError:
    return None


def get_full_name(locale: str) -> str:
  name = get_name(locale)
  return locale if name is None else f"{name} ({locale})"


def get_fallback(locale: str) -> str | None:
  try:
    return _raw_require("idhagnbot", "lang_fallback", locale)
  except KeyError:
    return None


def _get_locale_from_state(state: T_State) -> str:
  return state.get(LOCALE_KEY) or lang.current


Locale = Annotated[str, Depends(_get_locale_from_state)]


class Sentinel(Enum):
  SENTINEL = "sentinel"


def get_current_locale() -> str:
  if (locale := _current_locale.get(Sentinel.SENTINEL)) is not Sentinel.SENTINEL:
    return locale or lang.current
  if (matcher := current_matcher.get(None)) is not None:
    return matcher.state.get(LOCALE_KEY) or lang.current
  return lang.current


_raw_check_matcher = nonebot.message._check_matcher  # pyright: ignore[reportPrivateUsage]


async def _check_matcher(
  Matcher: type[Matcher],  # noqa: N803
  bot: Bot,
  event: Event,
  state: T_State,
  stack: AsyncExitStack | None = None,
  dependency_cache: T_DependencyCache | None = None,
) -> bool:
  token = _current_locale.set(state.get(LOCALE_KEY))
  try:
    return await _raw_check_matcher(Matcher, bot, event, state, stack, dependency_cache)
  finally:
    _current_locale.reset(token)


def _require(
  scope: str,
  type: str,  # noqa: A002
  locale: str | None = None,
) -> str:
  if locale is None:
    locale = get_current_locale()
  while locale:
    try:
      return _raw_require(scope, type, locale)
    except KeyError:
      locale = get_fallback(locale)
  identifier = f"{scope}:{type}"
  warnings.warn(f"Locale {locale} missing key: {identifier!r}", stacklevel=2)
  return f"__{identifier}__"


nonebot.message._check_matcher = _check_matcher  # ty:ignore[invalid-assignment]
lang.require = _require  # ty:ignore[invalid-assignment]


class BoundLang(Protocol):
  def __call__(self, key: str, locale: str | None = None, /) -> str: ...


def bound_lang(namespace: str) -> BoundLang:
  def require(key: str, locale: str | None = None, /) -> str:
    return lang.require(namespace, key, locale)

  return require


L = bound_lang("idhagnbot")


def apply_i18n(text: str, locale: str | None = None) -> str:
  def translate(match: re.Match[str]) -> str:
    return lang.require(match[1], match[2], locale)

  return _I18N_PATTERN.sub(translate, text)
