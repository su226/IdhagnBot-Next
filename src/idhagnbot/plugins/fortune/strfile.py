import array
import struct
import sys
from dataclasses import dataclass
from enum import IntFlag
from io import StringIO
from typing import BinaryIO, TextIO


class StrFileFlag(IntFlag):
  RANDOM = 1 << 0
  ORDERED = 1 << 1
  ROTATED = 1 << 2


@dataclass
class StrFile:
  version: int
  numstr: int
  longlen: int
  shortlen: int
  flags: StrFileFlag
  delim: str

  @property
  def random(self) -> bool:
    return StrFileFlag.RANDOM in self.flags

  @random.setter
  def random(self, value: bool) -> None:
    self.flags = self.flags & ~StrFileFlag.RANDOM | value

  @property
  def ordered(self) -> bool:
    return bool(self.flags & StrFileFlag.ORDERED)

  @ordered.setter
  def ordered(self, value: bool) -> None:
    self.flags = self.flags & ~StrFileFlag.ORDERED | value << 1

  @property
  def rotated(self) -> bool:
    return bool(self.flags & StrFileFlag.ROTATED)

  @rotated.setter
  def rotated(self, value: bool) -> None:
    self.flags = self.flags & ~StrFileFlag.ROTATED | value << 2


def read_header(f: BinaryIO) -> StrFile:
  version, count, maxlen, minlen, flags, delim = struct.unpack("!IIIIIcxxx", f.read(24))
  return StrFile(version, count, maxlen, minlen, StrFileFlag(flags), delim.decode())


def read_offset(f: BinaryIO, i: int) -> int:
  f.seek(24 + i * 4)
  return struct.unpack("!I", f.read(4))[0]


# array.array is not generic, but pyright allow this
def read_offsets(f: BinaryIO) -> "array.array[int]":
  f.seek(24)
  offsets = array.array("I", f.read())
  if sys.byteorder == "little":
    offsets.byteswap()  # strfile is always network(big) endian
  return offsets


# this doesn't handle rot13, use `codecs.decode(text, "rot13")`
def read_raw_text(f: TextIO, delim: str) -> str:
  delim_with_endline = delim + "\n"
  buf = StringIO()
  line = f.readline()
  while line and line not in (delim, delim_with_endline):
    buf.write(line)
    line = f.readline()
  return buf.getvalue()
