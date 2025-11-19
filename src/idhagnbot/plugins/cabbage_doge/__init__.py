import asyncio
import random
from pathlib import Path

import nonebot
from PIL import Image, ImagePalette

from idhagnbot.color import RGB, blend, parse, split_rgb
from idhagnbot.command import CommandBuilder
from idhagnbot.help import COMMAND_PREFIX
from idhagnbot.image import to_segment
from idhagnbot.message import send_image_or_animation

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, MultiVar
from nonebot_plugin_alconna import Image as ImageSeg

DIR = Path(__file__).resolve().parent
IMAGES = 50
DURATION = 75
MIDPOINT = 172


cabbage_doge = (
  CommandBuilder()
  .node("cabbage_doge")
  .parser(
    Alconna(
      "菜狗",
      Args["colors", MultiVar(str, "*")],
      meta=CommandMeta(
        "生成彩色菜狗 GIF",
        usage=f"""\
{COMMAND_PREFIX}菜狗 - 生成随机颜色的菜狗
{COMMAND_PREFIX}菜狗 <颜色> - 生成指定颜色的菜狗
{COMMAND_PREFIX}菜狗 <多个颜色> - 生成渐变色的菜狗
颜色可以是16进制，也可以是CSS颜色""",
        example=f"{COMMAND_PREFIX}菜狗 red",
      ),
    ),
  )
  .build()
)


@cabbage_doge.handle()
async def _(colors: tuple[str, ...]) -> None:
  color_values = []
  for i in colors:
    value = parse(i)
    if value is None:
      await cabbage_doge.finish(f"无效的颜色: {i}")
    color_values.append(split_rgb(value))
  if not color_values:
    color_values.append(split_rgb(random.randint(0, 0xFFFFFF)))

  def make() -> ImageSeg:
    frames = list[Image.Image]()
    for i in range(IMAGES):
      index, ratio = divmod(i / (IMAGES - 1) * (len(color_values) - 1), 1)
      index = int(index)
      if index + 1 >= len(color_values):
        # 防止到最后一个颜色时越界
        value = color_values[index]
      else:
        value = blend(color_values[index + 1], color_values[index], ratio)
      im = Image.open(DIR / f"{i}.png")
      upper_total = 255 - MIDPOINT
      palette = im.getpalette()
      new_palette = bytearray()
      assert palette
      for j in range(0, len(palette), 3):
        new_palette.extend(
          blend(value, (0, 0, 0), palette[j] / MIDPOINT)
          if palette[j] <= MIDPOINT
          else blend((255, 255, 255), value, (palette[j] - MIDPOINT) / upper_total),
        )
      im.putpalette(new_palette)
      frames.append(im)
    return to_segment(frames, DURATION)

  await send_image_or_animation(await asyncio.to_thread(make))
