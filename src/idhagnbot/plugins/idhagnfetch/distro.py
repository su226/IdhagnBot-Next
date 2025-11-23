import re
import sys
from collections.abc import Iterable
from pathlib import Path

if sys.version_info >= (3, 10):
  from platform import freedesktop_os_release
else:
  _os_release_candidates = ("/etc/os-release", "/usr/lib/os-release")
  _os_release_cache = None

  def _parse_os_release(lines: Iterable[str]) -> dict[str, str]:
    # These fields are mandatory fields with well-known defaults
    # in practice all Linux distributions override NAME, ID, and PRETTY_NAME.
    info = {
      "NAME": "Linux",
      "ID": "linux",
      "PRETTY_NAME": "Linux",
    }

    # NAME=value with optional quotes (' or "). The regular expression is less
    # strict than shell lexer, but that's ok.
    os_release_line = re.compile(
      "^(?P<name>[a-zA-Z0-9_]+)=(?P<quote>[\"']?)(?P<value>.*)(?P=quote)$",
    )
    # unescape five special characters mentioned in the standard
    os_release_unescape = re.compile(r"\\([\\\$\"\'`])")

    for line in lines:
      mo = os_release_line.match(line)
      if mo is not None:
        info[mo.group("name")] = os_release_unescape.sub(r"\1", mo.group("value"))

    return info

  def freedesktop_os_release() -> dict[str, str]:
    # Return operation system identification from freedesktop.org os-release
    global _os_release_cache

    if _os_release_cache is None:
      errno = None
      for candidate in _os_release_candidates:
        try:
          with Path(candidate).open(encoding="utf-8") as f:
            _os_release_cache = _parse_os_release(f)
          break
        except OSError as e:
          errno = e.errno
      else:
        raise OSError(errno, f"Unable to read files {', '.join(_os_release_candidates)}")

    return _os_release_cache.copy()


def get_distro() -> str:
  os_release = freedesktop_os_release()
  return os_release["PRETTY_NAME"]
