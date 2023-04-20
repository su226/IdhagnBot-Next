import argparse
import dataclasses
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import (
  Any, ClassVar, Generic, Iterable, List, Literal, Optional, Sequence, Type, TypeVar, Union
)

import nonebot
from nonebot.adapters import Message, MessageSegment
from nonebot.consts import SHELL_ARGS, SHELL_ARGV
from nonebot.dependencies import Dependent
from nonebot.exception import ParserExit
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, Depends, RawCommand
from nonebot.permission import Permission
from nonebot.rule import (
  TRIE_VALUE, ArgumentParser as NBArgumentParser, CommandRule, Rule, TrieRule, parser_message
)
from nonebot.typing import T_Handler, T_PermissionChecker, T_RuleChecker, T_State

__all__ = (
  "split", "HelpFormatter", "ShellCommandRule", "ArgumentParser", "parser_prog", "NoArg",
  "PlainTextOnly", "on_prefix_command"
)
_TSegment = TypeVar("_TSegment", bound=MessageSegment)
_WHITESPACE = 0
_TEXT = 1
_SEGMENT = 2
parser_prog: ContextVar[str] = ContextVar("parser_prog", default="")


@dataclasses.dataclass
class _TokenWhitespace:
  type: ClassVar[Literal[0]] = _WHITESPACE
  whitespace: str


@dataclasses.dataclass
class _TokenText:
  type: ClassVar[Literal[1]] = _TEXT
  text: str


@dataclasses.dataclass
class _TokenSegment(Generic[_TSegment]):
  type: ClassVar[Literal[2]] = _SEGMENT
  segment: _TSegment


_Token = Union[_TokenWhitespace, _TokenText, _TokenSegment[_TSegment]]


def split(message: Iterable[_TSegment]) -> List[Union[str, MessageSegment]]:
  def append_ch(ch: str) -> None:
    if tokens and tokens[-1].type == _TEXT:
      tokens[-1].text += ch
    else:
      tokens.append(_TokenText(ch))

  tokens: List[_Token] = []
  for segment in message:
    if segment.is_text():
      text = str(segment)
      quote: Literal["", "'", "\""] = ""
      i = 0
      while i < len(text):
        ch = text[i]
        next_ch = text[i + 1] if i + 1 < len(text) else ""
        if quote:
          if ch == quote:
            quote = ""
          elif ch == "\\" and next_ch in (quote, "\\"):
            append_ch(next_ch)
            i += 1
          else:
            append_ch(ch)
        else:
          if ch.isspace():
            if tokens and tokens[-1].type == _WHITESPACE:
              tokens[-1].whitespace += ch
            else:
              tokens.append(_TokenWhitespace(ch))
          elif ch == "\\" and (next_ch in ("'", "\"", "\\") or next_ch.isspace()):
            append_ch(next_ch)
            i += 1
          elif ch in ("'", "\""):
            quote = ch
          else:
            append_ch(ch)
        i += 1
    else:
      tokens.append(_TokenSegment(segment))

  result: List[_Token] = []
  for token in tokens:
    if token.type == _TEXT:
      if result and result[-1].type == _WHITESPACE:
        token.text = result[-1].whitespace + token.text
        result[-1] = token
      else:
        result.append(token)
    elif token.type == _WHITESPACE:
      if result and result[-1].type == _TEXT:
        result[-1].text += token.whitespace
      else:
        result.append(token)
    else:
      result.append(token)

  return [
    token.text if token.type == _TEXT else
    token.whitespace if token.type == _WHITESPACE else
    token.segment
    for token in result
  ]


class HelpFormatter(argparse.RawTextHelpFormatter):
  def _format_action(self, action: argparse.Action) -> str:
    action_header = self._format_action_invocation(action)
    if action.help:
      return "{}{} :: {}\n".format(self._current_indent * " ", action_header, action.help)
    else:
      return '{}{}\n'.format(self._current_indent * " ", action_header)


class ArgumentParser(NBArgumentParser):
  def __init__(
    self,
    prog: Optional[str] = "__cmd__",
    usage: Optional[str] = None,
    description: Optional[str] = None,
    epilog: Optional[str] = None,
    parents: Sequence[argparse.ArgumentParser] = [],
    formatter_class: "argparse._FormatterClass" = HelpFormatter,
    prefix_chars: str = "-",
    fromfile_prefix_chars: Optional[str] = None,
    argument_default: Any = None,
    conflict_handler: str = "error",
    add_help: bool = True,
    allow_abbrev: bool = False,  # 和标准库里默认为 True 不同
  ) -> None:
    super().__init__(
      prog,
      usage,
      description,
      epilog,
      parents,
      formatter_class,
      prefix_chars,
      fromfile_prefix_chars,
      argument_default,
      conflict_handler,
      add_help,
      allow_abbrev,
    )

  def _get_formatter(self) -> argparse.HelpFormatter:
    if prog := parser_prog.get():
      return self.formatter_class(prog=prog)
    return super()._get_formatter()


class ShellCommandRule:
  __slots__ = "parser",

  def __init__(self, parser: ArgumentParser):
    self.parser = parser

  async def __call__(
    self,
    state: T_State,
    cmd: Optional[str] = RawCommand(),
    msg: Optional[Message] = CommandArg(),
  ) -> bool:
    if cmd is None or msg is None:
      return False

    state[SHELL_ARGV] = split(msg)
    t1 = parser_message.set("")
    t2 = parser_prog.set(cmd)
    try:
      args = self.parser.parse_args(state[SHELL_ARGV])
      state[SHELL_ARGS] = args
    except argparse.ArgumentError as e:
      state[SHELL_ARGS] = ParserExit(status=2, message=str(e).replace("__cmd__", cmd))
    except ParserExit as e:
      state[SHELL_ARGS] = e
      if e.message:
        e.message = e.message.replace("__cmd__", cmd)
    finally:
      parser_message.reset(t1)
      parser_prog.reset(t2)
    return True


def NoArg() -> None:
  async def _noarg(cmd: str = RawCommand(), arg: Message = CommandArg()) -> None:
    if arg.extract_plain_text().strip() or any(not seg.is_text() for seg in arg):
      await Matcher.send(f"{cmd}: 警告: 该命令不接受参数")
  return Depends(_noarg)


def PlainTextOnly() -> str:
  async def _plaintext_only(cmd: str = RawCommand(), arg: Message = CommandArg()) -> str:
    types = set(seg.type for seg in arg if not seg.is_text())
    if types:
      await Matcher.send(f"{cmd}: 警告: 该命令只接受纯文本参数，发现 {'、'.join(types)}")
    return arg.extract_plain_text()
  return Depends(_plaintext_only)


def on_prefix_command(
  prefix: str,
  command: str,
  rule: Optional[Union[Rule, T_RuleChecker]] = None,
  force_whitespace: Optional[Union[str, bool]] = None,
  *,
  permission: Optional[Union[Permission, T_PermissionChecker]] = None,
  handlers: Optional[List[Union[T_Handler, Dependent]]] = None,
  temp: bool = False,
  expire_time: Optional[Union[datetime, timedelta]] = None,
  priority: int = 1,
  block: bool = False,
  state: Optional[T_State] = None,
) -> Type[Matcher]:
  '''
  只能使用指定前缀而非配置文件里 COMMAND_START 里前缀的指令。
  适用于 Telegram 的 /start 等固定的指令。
  '''
  TrieRule.add_prefix(f"{prefix}{command}", TRIE_VALUE(prefix, (command,)))
  return nonebot.on_message(
    Rule(CommandRule([(command,)], force_whitespace)) & rule,
    permission=permission,
    handlers=handlers,
    temp=temp,
    expire_time=expire_time,
    priority=priority,
    block=block,
    state=state,
    _depth=1,  # type: ignore
  )
