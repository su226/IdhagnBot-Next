# 🐱🤖✨ IdhagnBot-Next

一个以娱乐功能为主的机器人，跨平台 [IdhagnBot](https://github.com/su226/IdhagnBot) 移植版，目前支持 OneBot 和 Satori 协议，支持 QQ（userbot）和 Telegram 平台。

*本项目以[我的兽设](https://legacy.su226.eu.org/2021/07/24/my-fursona/)命名，主要服务我自己的 [QQ 群](https://qm.qq.com/cgi-bin/qm/qr?k=USDC9Yc0PPxBHHIVp5KIoHYSmuBHJK2u) 和 [TG 群](https://t.me/@su226g)，也会往我的 [TG 频道](https://t.me/@su226c) 里推送白嫖资讯。*

## 安装

以 [uv](https://docs.astral.sh/uv/) 为例，创建一个空项目，然后根据需要安装驱动器、适配器、[数据库后端](https://github.com/nonebot/plugin-orm)、IdhagnBot 本体和附加功能：

由于 NoneBot 2 Telegram 适配器自身存在一定问题，建议使用 Satori 适配器搭配 [mtproto-satori](https://github.com/su226/mtproto-satori) 使用，即使你使用的是机器人账号。

```shell
mkdir bot
cd bot
uv init --vcs none --no-readme
# 根据需要修改下一条命令
uv add nonebot2[fastapi,aiohttp] nonebot-adapter-onebot nonebot-adapter-satori nonebot-plugin-orm[default] https://github.com/su226/IdhagnBot-Next.git[crypto,psutil,cv2,jsonc]
```

您也可以加入第三方插件，比如我自己还加入了 [nonebot-plugin-prometheus](https://github.com/suyiiyii/nonebot-plugin-prometheus)，但不保证与本项目的集成良好。

在 pyproject.toml 的最后加入以下内容，配置插件和适配器列表。

```toml
[tool.nonebot]
plugin_dirs = []
builtin_plugins = []

[tool.nonebot.plugins]
"@local" = ["idhagnbot"]

[tool.nonebot.adapters]
"@local" = []
nonebot-adapter-onebot = [{name = "OneBot V11", module_name = "nonebot.adapters.onebot.v11"}]
nonebot-adapter-satori = [{name = "Satori", module_name = "nonebot.adapters.satori"}]
```

创建 NoneBot2 配置文件 .env，根据需要修改以下内容。

```dotenv
LOG_LEVEL=INFO
DRIVER=~fastapi+~aiohttp
SATORI_CLIENTS='[{"host":"localhost","port":5140,"path":"/satori","token":"1234567890abcdef"}]'
ONEBOT_WS_URLS='["ws://127.0.0.1:8080"]'
ONEBOT_ACCESS_TOKEN='1234567890abcdef'
SUPERUSERS=["onebot:1234567890"]
COMMAND_START=["/"]
LOCALSTORE_USE_CWD=true
APSCHEDULER_AUTOSTART=true  # 必须要有这一项
SQLALCHEMY_DATABASE_URL=postgresql+psycopg:///idhagnbot  # 如果使用 nonebot-plugin-orm[default] 则无需这一项
```

最后创建数据库表并运行。

```shell
uvx --from nb-cli nb orm upgrade
uvx --from nb-cli nb run
```

## 特别感谢

IdhagnBot-Next 的诞生离不开以下项目带来的启发和参考。
* [NoneBot2](https://v2.nonebot.dev/)
* [nonebot-plugin-alconna](https://github.com/nonebot/plugin-alconna)、[nonebot-plugin-uninfo](http://github.com/RF-Tar-Railt/nonebot-plugin-uninfo)，极大地简化了跨平台开发的难度。
* [meme-generator](https://github.com/MemeCrafters/meme-generator)、[Emoji Kitchen](https://github.com/xsalazar/emoji-kitchen)
* 以及其他参考过的 NoneBot2 插件和用到的在线 API。
