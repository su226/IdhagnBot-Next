from typing import TYPE_CHECKING, Any

from pydantic import BaseModel


class Model(BaseModel, extra="allow"):
  if TYPE_CHECKING:
    def __getattr__(self, key: str) -> Any: ...

  def __getitem__(self, key: str) -> Any:
    try:
      return getattr(self, key)
    except AttributeError as e:
      raise KeyError from e
