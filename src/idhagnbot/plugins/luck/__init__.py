import json
import math
import random
from datetime import date
from pathlib import Path

import cairo
from anyio.to_thread import run_sync
from arclet.alconna import Alconna, CommandMeta
from arclet.entari import Image as ImageSeg
from arclet.entari import MessageChain, Session, command
from arclet.letoderea import propagate
from entari_plugin_database import AsyncSession, Base
from entari_plugin_permission import require_permission
from PIL import Image, ImageEnhance, ImageFilter
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.color import blend
from idhagnbot.image import SCALE_RESAMPLE, open_url, paste, square, to_segment
from idhagnbot.text import escape, render


class Action(BaseModel):
    name: str
    do: str
    dont: str


with (Path(__file__).parent / "actions.json").open() as f:
    DATA = TypeAdapter(dict[str, Action]).validate_json(f.read())
    KEYS = list(DATA)
COLOR_GREEN = (105, 240, 174)
COLOR_YELLOW = (255, 255, 0)
COLOR_RED = (255, 82, 82)
ARC_TOP = 64
ARC_RADIUS = 192
ARC_WIDTH = 24
ARC_BOTTOM = ARC_TOP + ARC_RADIUS
DO_DONT_GAP = 64
DO_DONT_TOP = ARC_BOTTOM + DO_DONT_GAP
DO_DONT_FONT_SIZE = 24


class Luck(Base):
    __tablename__ = "idhagnbot_luck_luck"
    platform: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)
    date: Mapped[date]
    value: Mapped[int]
    do: Mapped[str]
    dont: Mapped[str]


def get_name(value: int) -> str:
    if value < 10:  # [0, 9]
        return "大凶"
    if value < 25:  # [10, 24]
        return "凶"
    if value < 45:  # [25, 44]
        return "小凶"
    if value < 56:  # [45, 55]
        return "平"
    if value < 76:  # [56, 75]
        return "小吉"
    if value < 91:  # [76, 90]
        return "吉"
    if value < 101:  # [91, 100]
        return "大吉"
    raise ValueError("无效运气值")


def generate_luck(luck: Luck | None, platform: str, user_id: str, today: date) -> Luck:
    value = random.randint(0, 100)
    if value > 90:
        do = random.sample(KEYS, 2)
        dont = []
    elif value < 10:
        do = []
        dont = random.sample(KEYS, 2)
    else:
        do_dont = random.sample(KEYS, 4)
        do = do_dont[:2]
        dont = do_dont[2:]
    if luck is not None:
        luck.date = today
        luck.value = value
        luck.do = json.dumps(do)
        luck.dont = json.dumps(dont)
        return luck
    return Luck(
        platform=platform,
        user_id=user_id,
        date=today,
        value=value,
        do=json.dumps(do),
        dont=json.dumps(dont),
    )


luck = Alconna(
    "luck",
    meta=CommandMeta(
        extra={
            "idhagnbot_i18n_description": "idhagnbot_luck:command_brief_luck",
            "idhagnbot_i18n_names": {
                "luck": "en-US",
                "运势": "zh-CN",
            },
        },
    ),
)
luck.shortcut("运势", command="luck")


@command.on(luck)
@propagate(require_permission("idhagnbot.luck", prompt=True))
async def handle_luck(session: Session, db: AsyncSession) -> MessageChain:
    today = date.today()
    luck = await db.get(Luck, (session.account.platform, session.user.id))
    if not luck or luck.date != today:
        luck = generate_luck(luck, session.account.platform, session.user.id, today)
        value = luck.value
        do = json.loads(luck.do)
        dont = json.loads(luck.dont)
        db.add(luck)
        await db.commit()
    else:
        value = luck.value
        do = json.loads(luck.do)
        dont = json.loads(luck.dont)

    r = value / 100
    avatar = (
        None
        if session.user.avatar is None
        else await open_url(str(session.account.ensure_url(session.user.avatar)))
    )

    def make() -> ImageSeg:
        im = Image.new("RGB", (640, 640), (255, 255, 255))
        nonlocal avatar
        if avatar is not None:
            avatar = square(avatar)
            avatar = avatar.resize((640, 640), SCALE_RESAMPLE)
            paste(im, avatar)
            im = im.filter(ImageFilter.GaussianBlur(8))
        im = ImageEnhance.Brightness(im).enhance(0.5)

        color = (
            blend(COLOR_GREEN, COLOR_YELLOW, (r - 0.5) * 2)
            if r > 0.5
            else blend(COLOR_YELLOW, COLOR_RED, r * 2)
        )

        with cairo.ImageSurface(
            cairo.FORMAT_ARGB32,
            ARC_RADIUS * 2,
            ARC_RADIUS,
        ) as surface:
            cr = cairo.Context(surface)
            radius = ARC_RADIUS - ARC_WIDTH / 2
            cr.set_line_width(16)
            cr.arc(ARC_RADIUS, ARC_RADIUS, radius, -math.pi, 0)
            cr.set_source_rgba(1, 1, 1, 0.2)
            cr.stroke()
            cr.new_path()
            cr.arc(ARC_RADIUS, ARC_RADIUS, radius, -math.pi, -math.pi * (1 - r))
            cr.set_source_rgba(color[0] / 255, color[1] / 255, color[2] / 255, 1)
            cr.stroke()
            paste(im, surface, (im.width // 2, ARC_TOP), (0.5, 0))

        text_im = render(
            f"{value}\n{get_name(value)}",
            "sans bold",
            48,
            color=color,
            align="m",
        )
        paste(im, text_im, (im.width // 2, ARC_BOTTOM), (0.5, 1))

        if not dont:
            text_im = render(
                "忌\n<span color='#69f0ae' size='150%'>诸事皆宜</span>",
                "sans",
                24,
                markup=True,
                color=(255, 255, 255),
                align="m",
            )
        else:
            text = "\n".join(
                f"<span color='#ff5252' size='150%'>{escape(DATA[item].name)}</span>\n"
                f"{escape(DATA[item].dont)}"
                for item in dont
            )
            text_im = render(
                f"忌\n{text}",
                "sans",
                DO_DONT_FONT_SIZE,
                markup=True,
                color=(255, 255, 255),
                align="m",
            )
        paste(im, text_im, (im.width // 4, DO_DONT_TOP), (0.5, 0))

        if not do:
            text_im = render(
                "宜\n<span color='#ff5252' size='150%'>诸事不宜</span>",
                "sans",
                DO_DONT_FONT_SIZE,
                markup=True,
                color=(255, 255, 255),
                align="m",
            )
        else:
            text = "\n".join(
                f"<span color='#69f0ae' size='150%'>{escape(DATA[item].name)}</span>\n"
                f"{escape(DATA[item].do)}"
                for item in do
            )
            text_im = render(
                f"宜\n{text}",
                "sans",
                DO_DONT_FONT_SIZE,
                markup=True,
                color=(255, 255, 255),
                align="m",
            )
        paste(im, text_im, (im.width * 3 // 4, DO_DONT_TOP), (0.5, 0))

        return to_segment(im)

    return MessageChain(await run_sync(make))
