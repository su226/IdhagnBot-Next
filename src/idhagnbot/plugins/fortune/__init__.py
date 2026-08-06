import codecs
import random
import re
from itertools import pairwise
from pathlib import Path

from arclet.alconna import (
    Alconna,
    Args,
    CommandMeta,
    MultiVar,
    Option,
    store_true,
)
from arclet.entari import command, metadata, plugin_config
from arclet.entari.command import Query
from arclet.letoderea import propagate
from entari_plugin_permission import require_permission
from pydantic import BaseModel

from idhagnbot.plugins.fortune.strfile import (
    StrFile,
    read_header,
    read_offsets,
    read_raw_text,
)


class Config(BaseModel):
    path: Path = Path("/usr/share/fortune")
    offensive: bool = False

    @property
    def offensive_path(self) -> Path:
        return self.path / "off"


metadata("", config=Config)
CONFIG = plugin_config(Config)
RE_033 = re.compile(r"\033\[(\d+;)*\d+m")


class StrFileChoice:
    path: Path
    header: StrFile
    offsets: list[int]

    def __init__(self, path: Path, length: int, long_or_short: bool | None) -> None:
        super().__init__()
        self.path = path
        with path.open("rb") as f:
            self.header = read_header(f)
            offsets = read_offsets(f)
        self.offsets = (
            list(offsets)
            if long_or_short is None
            else [
                curr_offset
                for curr_offset, next_offset in pairwise(offsets)
                # 如果文件末尾没有 delim 和 \n，最后一条的长度将会不准确
                if (next_offset - curr_offset - 3 >= length) == long_or_short
            ]
        )


@command.on(
    Alconna(
        "fortune",
        Args["file_or_prob", MultiVar(str, "*")],
        Option(
            "-a",
            action=store_true,
            default=False,
            dest="all",
            help_text="包括所有格言，冒犯的和不冒犯的",
        ),
        Option(
            "-c",
            action=store_true,
            default=False,
            dest="source",
            help_text="显示来源",
        ),
        Option(
            "-e",
            action=store_true,
            default=False,
            dest="equal",
            help_text="等概率选择文件（不使用格言数量加权）",
        ),
        Option(
            "-f",
            action=store_true,
            default=False,
            dest="files",
            help_text="输出文件列表",
        ),
        Option(
            "-l",
            action=store_true,
            default=False,
            dest="long",
            help_text="仅限长格言",
        ),
        Option(
            "-n",
            Args["length", int, 160],
            dest="limit",
            compact=True,
            help_text="多长算长？",
        ),
        Option(
            "-o",
            action=store_true,
            default=False,
            dest="offensive",
            help_text="仅限冒犯的格言",
        ),
        Option(
            "-s",
            action=store_true,
            default=False,
            dest="short",
            help_text="仅限短格言",
        ),
        meta=CommandMeta("输出一条随机且希望有趣的格言"),
    ),
)
@propagate(require_permission("idhagnbot.fortune", prompt=True))
async def handle_fortune(
    *,
    file_or_prob: tuple[str, ...],
    all: bool,  # noqa: A002
    source: bool,
    equal: bool,
    files: bool,
    long: bool,
    length: Query[int] = Query("limit.length", 160),
    offensive: bool,
    short: bool,
) -> str:
    prob = None
    files_with_prob = list[tuple[StrFileChoice, float]]()
    files_without_prob = list[StrFileChoice]()
    if long:
        long_or_short = True
    elif short:
        long_or_short = False
    else:
        long_or_short = None
    for item in file_or_prob:
        if item.endswith("%"):
            try:
                prob = float(item[:-1]) / 100
            except ValueError:
                return "概率无效"
            if prob < 0 or prob > 1:
                return "概率无效"
            continue
        file = (CONFIG.path / f"{item}.dat").resolve()
        if not file.is_relative_to(CONFIG.path) or not file.is_file():
            return "文件不存在"
        if file.parent.name == "off" and not CONFIG.offensive:
            return "禁止查看冒犯的格言"
        if prob:
            files_with_prob.append(
                (StrFileChoice(file, length.result, long_or_short), prob),
            )
            prob = None
        else:
            files_without_prob.append(StrFileChoice(file, length.result, long_or_short))
    if not files_with_prob and not files_without_prob:
        if all or offensive:
            if not CONFIG.offensive:
                return "禁止查看冒犯的格言"
            files_without_prob.extend(
                StrFileChoice(file, length.result, long_or_short)
                for file in CONFIG.offensive_path.iterdir()
                if file.suffix == ".dat"
            )
        if all or not offensive:
            files_without_prob.extend(
                StrFileChoice(file, length.result, long_or_short)
                for file in CONFIG.path.iterdir()
                if file.suffix == ".dat"
            )
    prob_sum = sum(x[1] for x in files_with_prob)
    if prob_sum > 1:
        return "概率之和大于 100%"
    if prob_sum < 1:
        if not files_without_prob:
            return "概率之和小于 100%"
        remaining_prob = 1 - prob_sum
        if equal:
            file_prob = remaining_prob / len(files_without_prob)
            files_with_prob.extend((file, file_prob) for file in files_without_prob)
        else:
            count_sum = sum(len(file.offsets) for file in files_without_prob)
            if count_sum == 0:
                file_prob = remaining_prob / len(files_without_prob)
                files_with_prob.extend((file, file_prob) for file in files_without_prob)
            else:
                files_with_prob.extend(
                    (file, len(file.offsets) / count_sum * remaining_prob)
                    for file in files_without_prob
                )
    if files:
        if not files_with_prob:
            return "似乎什么都没有"
        return "\n".join(
            f"{prob:.2%} {file.path.relative_to(CONFIG.path).with_suffix('')}"
            for file, prob in files_with_prob
        )
    file = random.choices(
        [x[0] for x in files_with_prob],
        [x[1] for x in files_with_prob],
    )[0]
    if not file.offsets:
        return "似乎什么都没有"
    with file.path.with_suffix("").open("r") as f:
        f.seek(random.choice(file.offsets))
        text = read_raw_text(f, file.header.delim).removesuffix("\n")
    if file.header.rotated:
        text = codecs.decode(text, "rot13")
    text = RE_033.sub("", text)
    if source:
        text = f"({file.path.relative_to(CONFIG.path).with_suffix('')})\n%\n{text}"
    return text
