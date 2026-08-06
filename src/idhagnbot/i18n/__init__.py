import warnings
from contextvars import ContextVar
from pathlib import Path
from typing import Protocol

from tarina.lang import lang

lang.load(Path(__file__).parent)
current_locale: ContextVar[str | None] = ContextVar(
    "idhagnbot_current_locale",
    default=None,
)


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


def get_current_locale() -> str:
    return current_locale.get() or lang.current


def get_locales(locale: str | None = None) -> list[str]:
    if locale is None:
        locale = get_current_locale()
    locales: list[str] = []
    while locale is not None:
        locales.append(locale)
        locale = get_fallback(locale)
    return locales


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
    return f"<L:{identifier}>"


lang.require = _require  # ty:ignore[invalid-assignment]


class BoundLang(Protocol):
    def __call__(self, key: str, locale: str | None = None, /) -> str: ...


def bound_lang(namespace: str) -> BoundLang:
    def require(key: str, locale: str | None = None, /) -> str:
        return lang.require(namespace, key, locale)

    return require
