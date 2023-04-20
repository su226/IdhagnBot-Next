# IdhagnBot Next
基于 NoneBot2 + OneBot V12 的跨平台聊天机器人。

## 平台支持
- QQ：WIP
- Telegram：WIP
- 其他平台：~~🕊️~~计划中

## 组件
- [IdhagnBot OBC](https://github.com/su226/IdhagnBot-Next/tree/main/idhagnbot/obc)：OneBot ~~V11~~/V12 ~~客户端~~/服务端协议库（划线部分敬请期待），注意这个组件的主要用途是实现 OneBot 协议端或中间件，这不是一个完整的机器人框架，若要实现机器人的业务逻辑，你应该优先考虑 NoneBot 或者 Koishi 等框架。
  - [IdhagnBot Telegram](https://github.com/su226/IdhagnBot-Next/tree/main/idhagnbot/ob12impl/telegram)：基于 IdhagnBot OBC 和 [Pyrogram](https://github.com/pyrogram/pyrogram) 的 Telegram OneBot V12 协议端。
- [IdhagnBot OICQ](https://github.com/su226/IdhagnBot-OICQ)：基于 [oicq-icalingua-plus-plus](https://github.com/Icalingua-plus-plus/oicq-icalingua-plus-plus) 的 QQ OneBot V12 实现。因为协议不同，本组件单独位于一个仓库。（注：使用 ICPP 的分支是因为 ICPP 的分支较 takayama-lily/oicq 更新较勤）
- [IdhagnBot Plugins](https://github.com/su226/IdhagnBot-Next/tree/main/idhagnbot/plugins)：插件库

## 功能
- Telegram `/start` 命令
- 🚧 更多功能正在开发中 🚧

## 协议
本仓库为 MIT，[IdhagnBot OICQ](https://github.com/su226/IdhagnBot-OICQ) 为 MPL-2.0。
