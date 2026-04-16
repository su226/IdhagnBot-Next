from contextlib import AsyncExitStack
from contextvars import ContextVar
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
  "get_fallback",
  "get_full_name",
  "get_name",
  "lang",
]
LOCALE_KEY = "_idhagnbot_locale"
lang.load(Path(__file__).parent)
_current_state = ContextVar[T_State]("_current_state")


def _raw_require(
  scope: str,
  type: str,  # noqa: A002
  locale: str,
) -> str:
  return lang._LangConfig__langs[locale][scope][type]  # pyright: ignore[reportAttributeAccessIssue]


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


def get_locale(state: T_State) -> str:
  return state.get(LOCALE_KEY) or lang.current


Locale = Annotated[str, Depends(get_locale)]


def _get_current_locale() -> str:
  if (state := _current_state.get(None)) is not None:
    return get_locale(state)
  if (matcher := current_matcher.get(None)) is not None:
    return get_locale(matcher.state)
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
  token = _current_state.set(state)
  try:
    return await _raw_check_matcher(Matcher, bot, event, state, stack, dependency_cache)
  finally:
    _current_state.reset(token)


def _require(
  scope: str,
  type: str,  # noqa: A002
  locale: str | None = None,
) -> str:
  if locale is None:
    locale = _get_current_locale()
  while locale:
    try:
      return _raw_require(scope, type, locale)
    except KeyError:
      locale = get_fallback(locale)
  identifier = f"{scope}:{type}"
  raise ValueError(f"Locale missing: {identifier!r}")


nonebot.message._check_matcher = _check_matcher  # pyright: ignore[reportPrivateUsage]
lang.require = _require


class BoundLang(Protocol):
  def __call__(self, key: str, locale: str | None = None, /) -> str: ...


def bound_lang(namespace: str) -> BoundLang:
  def require(key: str, locale: str | None = None, /) -> str:
    return lang.require(namespace, key, locale)

  return require


L = bound_lang("idhagnbot")
