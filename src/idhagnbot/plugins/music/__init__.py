from collections.abc import Callable, Sequence
from typing import Literal, TypeVar

import nonebot
from nonebot.adapters import Bot, Event

from idhagnbot.command import CommandBuilder
from idhagnbot.http import BROWSER_UA, get_session
from idhagnbot.image import to_segment
from idhagnbot.image.table import make_table
from idhagnbot.itertools import atake
from idhagnbot.plugins.music.sources.base import Music
from idhagnbot.plugins.music.sources.netease import NeteaseMusic
from idhagnbot.text import escape, render
from idhagnbot.waiter import prompt

nonebot.require("nonebot_plugin_alconna")
nonebot.require("nonebot_plugin_waiter")
from nonebot.typing import T_State
from nonebot_plugin_alconna import (
  Alconna,
  Args,
  File,
  MultiVar,
  Option,
  Query,
  Segment,
  Text,
  UniMessage,
  Voice,
)
from nonebot_plugin_alconna import Image as ImageSeg

TMusic = TypeVar("TMusic", bound=Music)
SendType = Literal["share", "link", "file", "voice"]
PAGE_SIZE = 10


def register(key: str, aliases: Sequence[str]) -> Callable[[type[TMusic]], type[TMusic]]:
  def do_register(music_t: type[TMusic]) -> type[TMusic]:
    matcher_t = (
      CommandBuilder()
      .node(f"music.{key}")
      .parser(
        Alconna(
          aliases[0],
          Args["keywords", MultiVar(str, "*")],
          Option("--id", Args["music_id", str]),
          Option("--type", Args["send_type", ["share", "link", "file", "voice"]]),
        ),
      )
      .aliases(set(aliases[1:]))
      .state({"music_t": music_t})
      .build()
    )
    matcher_t.handle()(handle_music)
    return music_t

  return do_register


def format_cell(text: str, unavailable: bool) -> str:
  markup = escape(text)
  return f"<s>{markup}</s>" if unavailable else markup


async def format_page(choices: Sequence[Music], count: int) -> UniMessage[Segment]:
  table = [
    [
      render("序号", "sans", 32),
      render("歌名", "sans", 32),
      render("歌手", "sans", 32),
      render("专辑", "sans", 32),
    ],
  ]
  for i, music in enumerate(choices[-PAGE_SIZE:], len(choices) - PAGE_SIZE + 1):
    table.append(
      [
        render(format_cell(str(i), music.unavailable), "sans", 32, markup=True),
        render(format_cell(music.name, music.unavailable), "sans", 32, markup=True),
        render(format_cell(" / ".join(music.artists), music.unavailable), "sans", 32, markup=True),
        render(format_cell(music.album, music.unavailable), "sans", 32, markup=True),
      ],
    )
  table_im = make_table(table, margin=32)
  info = ["发送序号选歌"]
  if any(x.unavailable for x in choices):
    info.append("部分歌曲不可用")
  if len(choices) < count:
    info.append("发送“下一页”加载下一页")
  info.append("发送“取消”放弃点歌")
  return UniMessage([to_segment(table_im), Text("，".join(info))])


async def prompt_music(music_t: type[TMusic], keyword: str) -> TMusic | None:
  result = await music_t.search(keyword)
  if not result.count:
    await UniMessage("搜索结果为空").send()
    return None
  choices = [x async for x in atake(result.musics, PAGE_SIZE)]
  message = await format_page(choices, result.count)
  await message.send()
  while True:
    choice = await prompt()
    if not choice:
      return None
    if not all(x.is_text() for x in choice):
      await UniMessage("选择无效，发送“取消”放弃点歌").send()
      continue
    choice_text = choice.extract_plain_text()
    if choice_text == "取消":
      return None
    if choice_text == "下一页":
      choices.extend([x async for x in atake(result.musics, PAGE_SIZE)])
      message = await format_page(choices, result.count)
      await message.send()
      continue
    try:
      choice_num = int(choice_text) - 1
    except ValueError:
      await UniMessage("选择无效，发送“取消”放弃点歌").send()
      continue
    if not 0 <= choice_num < len(choices):
      await UniMessage("选择无效，发送“取消”放弃点歌").send()
      continue
    return choices[choice_num]


async def fetch_audio(url: str) -> bytes:
  async with get_session().get(url, headers={"User-Agent": BROWSER_UA}) as response:
    return await response.read()


async def handle_music(
  *,
  bot: Bot,
  event: Event,
  state: T_State,
  keywords: tuple[str, ...],
  music_id: Query[str] = Query("id.music_id"),
  send_type: Query[SendType] = Query("type.send_type"),
) -> None:
  adapter = bot.adapter.get_name()
  if send_type.available:
    if send_type.result == "share" and adapter != "OneBot V11":
      await UniMessage("当前平台不支持发送分享卡片").send()
      return
    send_type_value = send_type.result
  elif adapter == "OneBot V11":
    send_type_value = "share"
  else:
    send_type_value = "file"
  music_t: type[Music] = state["music_t"]
  if music_id.available:
    try:
      music = await music_t.from_id(music_id.result)
    except ValueError as e:
      await UniMessage(str(e)).send()
      return
  elif keywords:
    music = await prompt_music(music_t, " ".join(keywords))
    if not music:
      return
  else:
    await UniMessage("请指定关键词或者 ID").send()
    return
  if music.unavailable:
    await UniMessage("抱歉，这首歌不可用").send()
    return
  if send_type_value == "share":
    from nonebot.adapters.onebot.v11 import MessageSegment

    audio_url = await music.get_audio_url()
    await bot.send(
      event,
      MessageSegment.music_custom(
        music.detail_url,
        audio_url.url,
        music.name,
        " / ".join(music.artists),
        await music.get_cover_url(),
      ),
    )
  elif send_type_value == "link":
    audio_url = await music.get_audio_url()
    await UniMessage(
      [
        ImageSeg(url=await music.get_cover_url()),
        Text(
          f"{music.name} - {' / '.join(music.artists)}\n"
          f"出自《{music.album}》\n"
          f"详情：{music.detail_url}\n"
          f"直链：{audio_url.url}",
        ),
      ],
    ).send()
  elif send_type_value == "file":
    audio_url = await music.get_audio_url()
    audio = await fetch_audio(audio_url.url)
    await UniMessage(File(raw=audio, name=f"{music.name}.{audio_url.extension}")).send()
  elif send_type_value == "voice":
    audio_url = await music.get_audio_url()
    audio = await fetch_audio(audio_url.url)
    await UniMessage(Voice(raw=audio, name=f"{music.name}.{audio_url.extension}")).send()


register("netease", ["网易云音乐", "网易云点歌", "网易云", "163"])(NeteaseMusic)
