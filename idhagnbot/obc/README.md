# IdhagnBot OBC
OneBot ~~V11~~/V12 ~~客户端~~/服务端协议库（划线部分敬请期待），用于实现 OneBot 协议端或中间件。

参见：[IdhagnBot Telegram](https://github.com/su226/IdhagnBot-Next/tree/main/idhagnbot/ob12impl/telegram)

## 支持的连接方式
- [ ] HTTP
- [ ] HTTP WebHook
- [x] 正向 WebSocket
- [x] 反向 WebSocket

## 示例代码
```python
import asyncio
from typing import Optional

from idhagnbot.obc.v12.action import SendMessageParam, SendMessageResult
from idhagnbot.obc.v12.app import ActionResult, ActionResultTuple, App as BaseApp
from idhagnbot.obc.v12.driver.ws import WebSocketDriver
from idhagnbot.obc.v12.event import BotSelf, BotStatus, Status, Version

class App(BaseApp):
  def __init__(self) -> None:
    super().__init__()
    # 添加动作实现，BaseApp 已实现 get_supported_actions、get_status 和 get_version
    self.add_action(self.send_message)
    # 动作的名称和参数类型会从函数名和类型标注里获取，也可以手动指定
    self.add_action(self.send_message, "send_message", SendMessageParam)

  # get_version 和 get_status 是 abc.abstractmethod，必须实现
  async def get_version(self) -> Version:
    return Version(impl="impl-name", version="0.1.0", onebot_version="12")

  async def get_status(self) -> Status:
    return Status(good=True, bots=[
      BotStatus(self=BotSelf(platform="impl-platform", user_id="self-id"), online=True)
    ])

  async def setup(self) -> None:
    await super().setup()
    # 连接到机器人平台
    await self.connect_to_platform(...)
    # 当收到事件以后使用 emit 发送，BaseApp 已实现 HeartbeatEvent
    # 驱动器已实现连接时的 ConnectEvent 和 StatusUpdateEvent
    # 注意连接之后产生的 StatusUpdateEvent 仍然需要手动发送
    self.emit(...)

  async def shutdown(self) -> None:
    await super().shutdown()
    # 断开连接
    await self.disconnect_from_platform(...)

  async def send_message(
    self,
    params: SendMessageParam,
    _bot_self: Optional[BotSelf],
  ) -> ActionResultTuple[SendMessageResult]:
    # 返回码, 错误信息, 响应数据
    return 0, "", SendMessageResult(...)
    # 也可以使用 raise ActionResult
    raise ActionResult(0, "", SendMessageResult(...))


async with App(...) as app:
  # 反向 WebSocket 驱动器在指定地址时自动创建和启动 aiohttp.web.Application
  # 传入 aiohttp.web.Application 时需手动启动
  # 可以同时使用多个驱动器
  async with WebSocketDriver(app, ("127.0.0.1", "8080")) as driver:
    app.heartbeat = 5000  # 设置心跳事件间隔（单位：毫秒）
    while True:
      await asyncio.sleep(3600)
```
