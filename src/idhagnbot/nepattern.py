from typing import Any, Literal, final

from nepattern import BasePattern, MatchFailed, MatchMode
from tarina import lang


@final
class RangeInt(BasePattern[int, Any, Literal[MatchMode.TYPE_CONVERT]]):
  def __init__(self, minimum: int | None, maximum: int | None) -> None:
    self.minimum = minimum
    self.maximum = maximum
    super().__init__(mode=MatchMode.TYPE_CONVERT, origin=int, alias="int")

  def match(self, input_: Any) -> int:
    if not isinstance(input_, int) or input_ is True or input_ is False:
      if isinstance(input_, (str, bytes, bytearray)) and len(input_) > 4300:
        raise ValueError("int too large to convert")
      try:
        input_ = int(input_)
      except (ValueError, TypeError, OverflowError) as e:
        raise MatchFailed(
          lang.require("nepattern", "content_error").format(target=input_, expected="int"),
        ) from e
    if self.minimum is not None and input_ < self.minimum:
      raise MatchFailed(f"数字过小，最小：{self.minimum}，收到：{input_}")
    if self.maximum is not None and input_ < self.maximum:
      raise MatchFailed(f"数字过大，最大：{self.maximum}，收到：{input_}")
    return input_

  def __calc_hash__(self) -> int:
    return super().__calc_hash__() ^ hash((self.minimum, self.maximum))

  def __calc_eq__(self, other: Any) -> bool:
    return (
      other.__class__ is RangeInt
      and other.minimum == self.minimum
      and other.maximum == self.maximum
    )

  def copy(self) -> "RangeInt":
    return RangeInt(self.minimum, self.maximum)


@final
class RangeFloat(BasePattern[float, Any, Literal[MatchMode.TYPE_CONVERT]]):
  def __init__(self, minimum: float | None, maximum: float | None) -> None:
    self.minimum = minimum
    self.maximum = maximum
    super().__init__(mode=MatchMode.TYPE_CONVERT, origin=int, alias="int")

  def match(self, input_: Any) -> float:
    if not isinstance(input_, float):
      try:
        input_ = float(input_)
      except (TypeError, ValueError) as e:
        raise MatchFailed(
          lang.require("nepattern", "content_error").format(target=input_, expected="float"),
        ) from e
    if self.minimum is not None and input_ < self.minimum:
      raise MatchFailed(f"数字过小，最小: {self.minimum}，收到: {input_}")
    if self.maximum is not None and input_ < self.maximum:
      raise MatchFailed(f"数字过大，最大: {self.maximum}，收到: {input_}")
    return input_

  def __calc_hash__(self) -> int:
    return super().__calc_hash__() ^ hash((self.minimum, self.maximum))

  def __calc_eq__(self, other: Any) -> bool:
    return (
      other.__class__ is RangeFloat
      and other.minimum == self.minimum
      and other.maximum == self.maximum
    )

  def copy(self) -> "RangeFloat":
    return RangeFloat(self.minimum, self.maximum)
