# 🐱🤖✨ IdhagnBot-Next

一个以娱乐功能为主的机器人，跨平台 [IdhagnBot](https://github.com/su226/IdhagnBot) 移植版，使用 Satori 协议，在 QQ（[satori-python-onebot-adapter11](https://github.com/RF-Tar-Railt/satori-python)）和 Telegram（[mtproto-satori](https://github.com/su226/mtproto-satori) + 机器人账号）平台上经过测试。

*本项目以[我的兽设](https://legacy.su226.eu.org/2021/07/24/my-fursona/)命名，主要服务我自己的 [QQ 群](https://qm.qq.com/cgi-bin/qm/qr?k=USDC9Yc0PPxBHHIVp5KIoHYSmuBHJK2u) 和 [TG 群](https://t.me/@su226g)，也会往我的 [TG 频道](https://t.me/@su226c) 里推送白嫖资讯。*

## 安装

以 [uv](https://docs.astral.sh/uv/) 为例，创建一个空项目，然后根据需要安装[数据库后端](https://arclet.top/tutorial/entari/database.html)、IdhagnBot 本体和附加功能：

```shell
mkdir bot
cd bot
uv init --vcs none --no-readme
# 根据需要修改下一条命令
uv add aiosqlite https://github.com/su226/IdhagnBot-Next.git[...]
```

然后创建配置文件 entari.yml：

```yaml
basic: # 参见 Entari 文档以完成基础配置。
  network:
    - type: websocket
      host: localhost
      port: 5140
      path: ''
  ignore_self_message: true
  log:
    level: info
  prefix:
    - /
  schema: true
plugins: # 如需使用 SQLite 以外的数据库，或改变数据存储目录，请修改相应插件的配置
  $prefix:
    - key: ""
      plugins:
        - idhagnbot
  idhagnbot: {}
```

最后运行机器人：

```shell
uvx --from entari-cli entari run
```

## 特别感谢

IdhagnBot-Next 的诞生离不开以下项目带来的启发和参考。

* [Entari](github.com/ArcletProject/Entari)
* [meme-generator](https://github.com/MemeCrafters/meme-generator)、[Emoji Kitchen](https://github.com/xsalazar/emoji-kitchen)
* 以及其他参考过的机器人插件和用到的在线 API。
