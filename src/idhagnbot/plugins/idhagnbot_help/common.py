def normalize_path(*path: str) -> list[str]:
  result: list[str] = []
  for i in path:
    result.extend(x for x in i.split(".") if x)
  return result


def join_path(path: list[str]) -> str:
  if not path:
    return "."
  return ".".join(path)
