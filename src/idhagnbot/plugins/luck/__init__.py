import json
import math
import random
from collections.abc import Sequence
from datetime import date as datetype
from datetime import timedelta
from itertools import pairwise
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
from sqlalchemy import ForeignKeyConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from idhagnbot.color import blend, to_hex
from idhagnbot.image import SCALE_RESAMPLE, open_url, paste, square, to_segment
from idhagnbot.plugins.record import User
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
SIZE = 640
ARC_TOP = 32
ARC_RADIUS = 192
ARC_WIDTH = 24
ARC_BOTTOM = ARC_TOP + ARC_RADIUS
DO_DONT_GAP = 32
DO_DONT_TOP = ARC_BOTTOM + DO_DONT_GAP
DO_DONT_FONT_SIZE = 24
CHART_GAP = 32
CHART_LINE_WIDTH = 2
CHART_LINES = 6
CHART_MARGIN_X = 16
CHART_DOT_RADIUS = 2
CHART_DAYS = 29


class Luck(Base):
    __tablename__ = "idhagnbot_luck_luck"
    platform: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)
    date: Mapped[datetype] = mapped_column(primary_key=True)
    value: Mapped[int]
    do: Mapped[str]
    dont: Mapped[str]
    __table_args__ = (
        ForeignKeyConstraint(("platform", "user_id"), (User.platform, User.id)),
    )


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


def generate_luck(
    platform: str,
    user_id: str,
    today: datetype,
) -> Luck:
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
    return Luck(
        platform=platform,
        user_id=user_id,
        date=today,
        value=value,
        do=json.dumps(do),
        dont=json.dumps(dont),
    )


def fritsch_carlson_tangents(points: Sequence[tuple[float, float]]) -> list[float]:
    n = len(points)
    delta = [(p2[1] - p1[1]) / (p2[0] - p1[0]) for p1, p2 in pairwise(points)]

    m = [0.0] * n
    m[0] = delta[0]
    m[n - 1] = delta[n - 2]
    for i in range(1, n - 1):
        if delta[i - 1] * delta[i] <= 0:
            m[i] = 0
        else:
            m[i] = (delta[i - 1] + delta[i]) / 2

    for i in range(n - 1):
        if delta[i] == 0:
            m[i] = 0
            m[i + 1] = 0
            continue
        a = m[i] / delta[i]
        b = m[i + 1] / delta[i]
        s = a * a + b * b
        if s > 9:
            t = 3 / math.sqrt(s)
            m[i] = t * a * delta[i]
            m[i + 1] = t * b * delta[i]

    return m


def smooth_curve(
    cr: cairo.Context,
    points: Sequence[tuple[float, float]],
    smooth: float = 1,
) -> None:
    n = len(points)
    if n == 1:
        cr.move_to(points[0][0], points[0][1])
        return
    if n == 2:
        cr.move_to(points[0][0], points[0][1])
        cr.line_to(points[1][0], points[1][1])
        return

    m = fritsch_carlson_tangents(points)
    cr.move_to(points[0][0], points[0][1])
    for i in range(n - 1):
        p1 = points[i]
        p2 = points[i + 1]
        h = p2[0] - p1[0]

        cp1x = p1[0] + h / 3 * smooth
        cp1y = p1[1] + (h / 3) * m[i] * smooth
        cp2x = p2[0] - h / 3 * smooth
        cp2y = p2[1] - (h / 3) * m[i + 1] * smooth

        cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])


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
    today = datetype.today()
    history_start = today - timedelta(CHART_DAYS)
    result = await db.execute(
        select(Luck)
        .where(
            Luck.platform == session.account.platform,
            Luck.user_id == session.user.id,
            Luck.date >= history_start,
            Luck.date <= today,
        )
        .order_by(Luck.date),
    )
    result = list(result.scalars())
    chart_values = []
    current_date = history_start
    i = 0
    while current_date <= today:
        if i < len(result) and result[i].date == current_date:
            chart_values.append(result[i].value)
            i += 1
        else:
            chart_values.append(None)
        current_date += timedelta(1)
    if result and result[-1].date == today:
        luck = result[-1]
        value = luck.value
        do = json.loads(luck.do)
        dont = json.loads(luck.dont)
    else:
        luck = generate_luck(session.account.platform, session.user.id, today)
        value = luck.value
        chart_values[-1] = value
        do = json.loads(luck.do)
        dont = json.loads(luck.dont)
        db.add(luck)
        await db.commit()

    r = value / 100
    avatar = (
        None
        if session.user.avatar is None
        else await open_url(str(session.account.ensure_url(session.user.avatar)))
    )

    def make() -> ImageSeg:
        im = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
        nonlocal avatar
        if avatar is not None:
            avatar = square(avatar)
            avatar = avatar.resize((SIZE, SIZE), SCALE_RESAMPLE)
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
            cr.set_source_rgb(color[0] / 255, color[1] / 255, color[2] / 255)
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

        do_color = to_hex(*COLOR_GREEN)
        dont_color = to_hex(*COLOR_RED)

        if not dont:
            text_im = render(
                f"忌\n<span color='#{do_color}' size='150%'>诸事皆宜</span>",
                "sans",
                24,
                markup=True,
                color=(255, 255, 255),
                align="m",
            )
        else:
            text = "\n".join(
                f"<span color='#{dont_color}' size='150%'>{escape(DATA[item].name)}"
                f"</span>\n{escape(DATA[item].dont)}"
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
        text_height = text_im.height
        paste(im, text_im, (im.width // 4, DO_DONT_TOP), (0.5, 0))

        if not do:
            text_im = render(
                f"宜\n<span color='#{dont_color}' size='150%'>诸事不宜</span>",
                "sans",
                DO_DONT_FONT_SIZE,
                markup=True,
                color=(255, 255, 255),
                align="m",
            )
        else:
            text = "\n".join(
                f"<span color='#{do_color}' size='150%'>{escape(DATA[item].name)}"
                f"</span>\n{escape(DATA[item].do)}"
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
        text_height = max(text_height, text_im.height)
        paste(im, text_im, (im.width * 3 // 4, DO_DONT_TOP), (0.5, 0))

        chart_top = DO_DONT_TOP + text_height + CHART_GAP
        chart_height = SIZE - chart_top
        with cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, chart_height) as surface:
            cr = cairo.Context(surface)
            chart_content_top = CHART_LINE_WIDTH / 2
            chart_effective_height = chart_height - CHART_LINE_WIDTH
            chart_line_gap = chart_effective_height / (CHART_LINES - 1)
            y = chart_content_top
            for _ in range(CHART_LINES):
                cr.move_to(0, y)
                cr.line_to(SIZE, y)
                y += chart_line_gap
            cr.set_source_rgba(1, 1, 1, 0.2)
            cr.set_line_width(CHART_LINE_WIDTH)
            cr.stroke()

            n = len(chart_values)
            chart_content_left = CHART_MARGIN_X + CHART_DOT_RADIUS
            chart_effective_width = SIZE - CHART_MARGIN_X * 2 - CHART_DOT_RADIUS * 2
            chart_dot_gap = chart_effective_width / (n - 1)
            points = []
            for i, point_value in enumerate(chart_values):
                if point_value is None:
                    points.append(None)
                else:
                    point_r = point_value / 100
                    x = chart_content_left + chart_dot_gap * i
                    y = chart_content_top + chart_effective_height * (1 - point_r)
                    point_color = (
                        blend(COLOR_GREEN, COLOR_YELLOW, (point_r - 0.5) * 2)
                        if point_r > 0.5
                        else blend(COLOR_YELLOW, COLOR_RED, point_r * 2)
                    )
                    points.append((x, y, point_color))

            curve = []
            for point in points:
                if point is None:
                    if curve:
                        smooth_curve(cr, curve)
                    curve.clear()
                else:
                    curve.append(point[:2])
            if curve:
                smooth_curve(cr, curve)
            gradient = cairo.LinearGradient(
                0,
                chart_content_top,
                0,
                chart_content_top + chart_effective_height,
            )
            gradient.add_color_stop_rgb(
                0,
                COLOR_GREEN[0] / 255,
                COLOR_GREEN[1] / 255,
                COLOR_GREEN[2] / 255,
            )
            gradient.add_color_stop_rgb(
                0.5,
                COLOR_YELLOW[0] / 255,
                COLOR_YELLOW[1] / 255,
                COLOR_YELLOW[2] / 255,
            )
            gradient.add_color_stop_rgb(
                1,
                COLOR_RED[0] / 255,
                COLOR_RED[1] / 255,
                COLOR_RED[2] / 255,
            )
            cr.set_source(gradient)
            cr.stroke()

            for point in points:
                if point is not None:
                    cr.arc(point[0], point[1], CHART_DOT_RADIUS, 0, math.tau)
                    point_color = point[2]
                    cr.set_source_rgb(
                        point_color[0] / 255,
                        point_color[1] / 255,
                        point_color[2] / 255,
                    )
                    cr.fill()

            paste(im, surface, (0, chart_top))

        return to_segment(im)

    return MessageChain(await run_sync(make))
