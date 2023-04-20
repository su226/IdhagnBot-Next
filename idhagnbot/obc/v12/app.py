import abc
import asyncio
import inspect
from types import TracebackType
from typing import (
  Any, Awaitable, Callable, Coroutine, Dict, ForwardRef, Generic, Optional, Set, Tuple, Type,
  TypeVar
)
import uuid
import time

from loguru import logger
from pydantic import ValidationError, parse_obj_as
from pydantic.typing import evaluate_forwardref
from typing_extensions import Self

from idhagnbot.obc.v12.action import (
  GetStatusParam, GetStatusResult, GetSupportedActionsParam, GetSupportedActionsResult,
  GetVersionParam, GetVersionResult
)
from idhagnbot.obc.v12.event import BotSelf, Event, Status, Version, HeartbeatEvent

TParam = TypeVar("TParam")
TResult = TypeVar("TResult")
ActionResultTuple = Tuple[int, str, Optional[TResult]]
EventListener = Callable[[Event], Coroutine[Any, Any, None]]
ActionFunc = Callable[[TParam, Optional[BotSelf]], Awaitable[ActionResultTuple[Any]]]
StatusFunc = Callable[[], Awaitable[Status]]
VersionFunc = Callable[[], Awaitable[Version]]
HookFunc = Callable[[], Awaitable[None]]


class ActionResult(BaseException, Generic[TResult]):
  def __init__(self, retcode: int, message: str, data: TResult) -> None:
    super().__init__(retcode, message, data)
    self.retcode = retcode
    self.message = message
    self.data = data

  def to_tuple(self) -> ActionResultTuple[TResult]:
    return self.retcode, self.message, self.data


def _inspect_param_type(func: ActionFunc[TParam]) -> Type[TParam]:
  signature = inspect.signature(func)
  globalns = getattr(func, "__globals__", {})
  for param in signature.parameters.values():
    annotation = param.annotation
    if isinstance(annotation, str):
      annotation = evaluate_forwardref(ForwardRef(annotation), globalns, globalns)
    if annotation is not inspect.Parameter.empty:
      return annotation
  raise TypeError("No params type provided and cannot be inspected from function annotations.")


class App(abc.ABC):
  def __init__(self) -> None:
    self._actions: Dict[str, Tuple[Type[Any], ActionFunc[Any]]] = {}
    self._event_listeners: Set[EventListener] = set()
    self.__running = False
    self.add_action(self._get_supported_actions, "get_supported_actions")
    self.add_action(self._get_status, "get_status")
    self.add_action(self._get_version, "get_version")

  def add_action(
    self,
    func: ActionFunc[Any],
    name: Optional[str] = None,
    params: Optional[Type[Any]] = None,
  ) -> None:
    real_name = name or func.__name__
    real_params = params or _inspect_param_type(func)
    self._actions[real_name] = (real_params, func)
    self.__heartbeat = 0
    self.__heartbeat_timer: Optional[asyncio.TimerHandle] = None

  async def setup(self) -> None:
    if self.__running:
      raise ValueError("setup() already called.")
    self.__running = True

  async def __aenter__(self) -> Self:
    await self.setup()
    return self

  async def shutdown(self) -> None:
    if not self.__running:
      raise ValueError("shutdown() called before setup().")
    self.__running = False

  async def __aexit__(
    self,
    exctype: Optional[Type[BaseException]],
    exc: Optional[BaseException],
    tb: Optional[TracebackType],
  ) -> Optional[bool]:
    await self.shutdown()

  @property
  def running(self) -> bool:
    return self.__running

  def add_event_listener(self, listener: EventListener) -> None:
    self._event_listeners.add(listener)

  def remove_event_listener(self, listener: EventListener) -> None:
    self._event_listeners.remove(listener)

  def emit(self, event: Event) -> None:
    for listener in self._event_listeners:
      asyncio.create_task(listener(event))

  def emit_heartbeat(self) -> None:
    self.emit(HeartbeatEvent(
      id=str(uuid.uuid4()),
      time=time.time(),
      type="meta",
      detail_type="heartbeat",
      sub_type="",
      interval=self.__heartbeat,
    ))

  @property
  def heartbeat(self) -> int:
    return self.__heartbeat

  @heartbeat.setter
  def heartbeat(self, value: int) -> None:
    if value < 0:
      raise ValueError("Heartbeat interval must >= 0")
    if self.__heartbeat_timer:
      self.__heartbeat_timer.cancel()
    self.__heartbeat = value
    if value:
      self.__heartbeat_timer = asyncio.get_running_loop().call_later(
        self.__heartbeat / 1000,
        self.__do_heartbeat,
      )

  def __do_heartbeat(self) -> None:
    self.emit_heartbeat()
    self.__heartbeat_timer = asyncio.get_running_loop().call_later(
      self.__heartbeat / 1000,
      self.__do_heartbeat,
    )

  async def handle_action(
    self,
    action: str,
    params: Any,
    bot_self: Optional[BotSelf],
  ) -> ActionResultTuple[Any]:
    if action not in self._actions:
      return 10002, "Unsupported or unknown action.", None
    param_type, func = self._actions[action]
    try:
      parsed_params = parse_obj_as(param_type, params)
    except ValidationError as e:
      return 10003, f"Failed to parse params: {e}", None
    try:
      return await func(parsed_params, bot_self)
    except ActionResult as e:
      return e.to_tuple()
    except Exception as e:
      logger.exception(f"Action {action} raised an exception.")
      return 20002, f"Internal error: {e}", None

  @abc.abstractmethod
  async def get_status(self) -> Status: ...

  @abc.abstractmethod
  async def get_version(self) -> Version: ...

  async def _get_supported_actions(
    self,
    _param: GetSupportedActionsParam,
    _bot_self: Optional[BotSelf],
  ) -> ActionResultTuple[GetSupportedActionsResult]:
    return 0, "", list(self._actions)

  async def _get_status(
    self,
    _param: GetStatusParam,
    _bot_self: Optional[BotSelf],
  ) -> ActionResultTuple[GetStatusResult]:
    return 0, "", await self.get_status()

  async def _get_version(
    self,
    _param: GetVersionParam,
    _bot_self: Optional[BotSelf],
  ) -> ActionResultTuple[GetVersionResult]:
    return 0, "", await self.get_version()
