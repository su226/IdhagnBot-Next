from datetime import datetime, timezone

import nonebot

from idhagnbot.help import CategoryItem, CommandItem
from idhagnbot.permission import permission
from idhagnbot.third_party import epicgames as api

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Image, Text, UniMessage

CategoryItem.ROOT.add(CommandItem(["epicgames"], "查询 Epic Games 免费游戏"))
epicgames = nonebot.on_command("epicgames", permission=permission("epicgames"))


@epicgames.handle()
async def handle_epicgames() -> None:
  games = await api.get_free_games()
  if not games:
    await epicgames.finish("似乎没有可白嫖的游戏")
  games.sort(key=lambda x: x.end_date)
  now_date = datetime.now(timezone.utc)
  message = UniMessage()
  for game in games:
    end_str = game.end_date.astimezone().strftime("%Y-%m-%d %H:%M")
    if now_date > game.start_date:
      text = f"{game.title} 目前免费，截止到 {end_str}"
    else:
      start_str = game.start_date.astimezone().strftime("%Y-%m-%d %H:%M")
      text = f"{game.title} 将在 {start_str} 免费，截止到 {end_str}"
    if message:
      text = "\n" + text
    message.extend(
      [
        Text(text + f"\n{api.URL_BASE}{game.slug}\n"),
        Image(url=game.image),
      ],
    )
  await message.send()
