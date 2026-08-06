import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from arclet.alconna import Alconna, Args, MultiVar, Option
from arclet.entari import Audio, File, MessageChain, Session, Text, command
from arclet.entari import Image as ImageSeg
from arclet.entari.command import Query
from entari_plugin_permission import require_permission
from PIL import Image
from satori.element import Custom

from idhagnbot.http import BROWSER_UA, get_session
from idhagnbot.image import to_segment
from idhagnbot.image.table import Table
from idhagnbot.itertools import atake
from idhagnbot.plugins.music.sources.base import Music
from idhagnbot.plugins.music.sources.netease import NeteaseMusic
from idhagnbot.text import escape, render

SendType = Literal["share", "link", "file", "voice"]
PAGE_SIZE = 10


def render_cell(text: str, unavailable: bool) -> Image.Image:
    if unavailable:
        return render(f"<s>{escape(text)}</s>", "sans", 32, markup=True)
    return render(text, "sans", 32)


def format_page(choices: Sequence[Music], count: int) -> MessageChain:
    table = [
        [
            render("序号", "sans bold", 32),
            render("歌名", "sans bold", 32),
            render("歌手", "sans bold", 32),
            render("专辑", "sans bold", 32),
        ],
    ]
    start_idx = (len(choices) - 1) // PAGE_SIZE * PAGE_SIZE
    for i, music in enumerate(choices[start_idx:], start_idx + 1):
        table.append(
            [
                render_cell(str(i), music.unavailable),
                render_cell(music.name, music.unavailable),
                render_cell(" / ".join(music.artists), music.unavailable),
                render_cell(music.album, music.unavailable),
            ],
        )
    table = Table(table)
    table.margin = 32
    info = ["发送序号选歌"]
    if any(x.unavailable for x in choices):
        info.append("部分歌曲不可用")
    if len(choices) < count:
        info.append("发送“下一页”加载下一页")
    info.append("发送“取消”放弃点歌")
    return MessageChain([to_segment(table.render()), Text("，".join(info))])


async def prompt_music[TMusic: Music](
    session: Session,
    music_t: type[TMusic],
    keyword: str,
) -> TMusic | str | None:
    result = await music_t.search(keyword)
    if not result.count:
        return "搜索结果为空"
    choices = [x async for x in atake(result.musics, PAGE_SIZE)]
    message = await asyncio.to_thread(format_page, choices, result.count)
    choice = await session.prompt(message)
    while True:
        if not choice:
            return None
        if not all(isinstance(x, Text) for x in choice):
            choice = await session.prompt("选择无效，发送“取消”放弃点歌")
            continue
        choice_text = choice.extract_plain_text()
        if choice_text == "取消":
            return None
        if choice_text == "下一页":
            choices.extend([x async for x in atake(result.musics, PAGE_SIZE)])
            message = await asyncio.to_thread(format_page, choices, result.count)
            choice = await session.prompt(message)
            continue
        try:
            choice_num = int(choice_text) - 1
        except ValueError:
            choice = await session.prompt("选择无效，发送“取消”放弃点歌")
            continue
        if not 0 <= choice_num < len(choices):
            choice = await session.prompt("选择无效，发送“取消”放弃点歌")
            continue
        return choices[choice_num]


async def fetch_audio(url: str) -> bytes:
    async with get_session().get(url, headers={"User-Agent": BROWSER_UA}) as response:
        return await response.read()


@dataclass
class MusicHandler:
    music_t: type[Music]

    async def handle(
        self,
        session: Session,
        keywords: tuple[str, ...],
        music_id: Query[str] = Query("id.music_id"),
        send_type: Query[SendType] = Query("type.send_type"),
    ) -> str | MessageChain | None:
        if send_type.available:
            if send_type.result == "share" and session.account.platform != "onebot":
                return "当前平台不支持发送分享卡片"
            send_type_value = send_type.result
        elif session.account.platform == "onebot":
            send_type_value = "share"
        else:
            send_type_value = "file"
        if music_id.available:
            try:
                music = await self.music_t.from_id(music_id.result)
            except ValueError as e:
                return str(e)
        elif keywords:
            music = await prompt_music(session, self.music_t, " ".join(keywords))
            if not isinstance(music, Music):
                return music
        else:
            return "请指定关键词或者 ID"
        if music.unavailable:
            return "抱歉，这首歌不可用"
        if send_type_value == "share":
            audio_url = await music.get_audio_url()
            return MessageChain(
                Custom(
                    "onebot:music",
                    {
                        "type": "custom",
                        "url": music.detail_url,
                        "audio": audio_url.url,
                        "title": music.name,
                        "content": " / ".join(music.artists),
                        "image": await music.get_cover_url(),
                    },
                ),
            )
        if send_type_value == "link":
            audio_url = await music.get_audio_url()
            return MessageChain(
                [
                    ImageSeg(await music.get_cover_url()),
                    Text(
                        f"{music.name} - {' / '.join(music.artists)}\n"
                        f"出自《{music.album}》\n"
                        f"详情：{music.detail_url}\n"
                        f"直链：{audio_url.url}",
                    ),
                ],
            )
        if send_type_value == "file":
            audio_url = await music.get_audio_url()
            audio = await fetch_audio(audio_url.url)
            return MessageChain(
                File.of(raw=audio, name=f"{music.name}.{audio_url.extension}"),
            )
        if send_type_value == "voice":
            audio_url = await music.get_audio_url()
            audio = await fetch_audio(audio_url.url)
            return MessageChain(
                Audio.of(raw=audio, name=f"{music.name}.{audio_url.extension}"),
            )
        raise AssertionError("unreachable")


def register[TMusic: Music](
    key: str,
    aliases: Sequence[str],
) -> Callable[[type[TMusic]], type[TMusic]]:
    def do_register(music_t: type[TMusic]) -> type[TMusic]:
        cmd = Alconna(
            aliases[0],
            Args["keywords", MultiVar(str, "*")],
            Option("--id", Args["music_id", str]),
            Option("--type", Args["send_type", ["share", "link", "file", "voice"]]),
        )
        for alias in aliases[1:]:
            cmd.shortcut(alias, command=aliases[0])
        command.on(cmd)(MusicHandler(music_t).handle).propagate(
            require_permission(f"idhagnbot.music.{key}", prompt=True),
        )
        return music_t

    return do_register


register("netease", ["网易云音乐", "网易云点歌", "网易云", "163"])(NeteaseMusic)
