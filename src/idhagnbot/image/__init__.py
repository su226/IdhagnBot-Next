import math
from collections.abc import Generator, Sequence
from io import BytesIO
from typing import Any, Literal, Protocol, TypeVar, cast, overload

import cairo
import nonebot
from anyio.to_thread import run_sync
from nonebot import logger
from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageSequence, features
from pydantic import BaseModel

from idhagnbot import color
from idhagnbot.config import SharedConfig
from idhagnbot.http import get_session
from idhagnbot.url import path_from_url

nonebot.require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import Image as ImageSeg

__all__ = [
  "Anchor",
  "AnyImage",
  "Color",
  "PasteColor",
  "PerspectiveData",
  "PixelAccess",
  "Plane",
  "Point",
  "Quantize",
  "RemapTransform",
  "Resample",
  "ScaleResample",
  "Size",
  "background",
  "center_pad",
  "circle",
  "colorize",
  "contain_down",
  "flatten",
  "frames",
  "from_cairo",
  "get_resample",
  "get_scale_resample",
  "load",
  "open_url",
  "paste",
  "quantize",
  "replace",
  "resize_canvas",
  "resize_height",
  "resize_width",
  "rounded_rectangle",
  "sample_frames",
  "square",
  "to_cairo",
  "to_segment",
]


Resample = Literal["nearest", "bilinear", "bicubic"]
ScaleResample = Resample | Literal["box", "hamming", "lanczos"]
Quantize = Literal["mediancut", "maxcoverage", "fastoctree"]


class Config(BaseModel):
  resample: Resample = "bicubic"
  scale_resample: ScaleResample = "bicubic"
  libimagequant: bool = False
  quantize: Quantize = "mediancut"
  dither: bool = True


CONFIG = SharedConfig("image", Config)
Anchor = Literal["lt", "lm", "lb", "mt", "mm", "mb", "rt", "rm", "rb"]
Size = tuple[int, int]
Point = tuple[float, float]
Color = color.RGB | int
Plane = tuple[Point, Point, Point, Point]
PerspectiveData = tuple[float, float, float, float, float, float, float, float]
PasteColor = tuple[Color, Size]
AnyImage = Image.Image | cairo.ImageSurface
T = TypeVar("T")
_libimagequant_available: bool | None = None
_libimagequant_warned: bool = False


def get_resample() -> Image.Resampling:
  return Image.Resampling[CONFIG().resample.upper()]


def get_scale_resample() -> Image.Resampling:
  return Image.Resampling[CONFIG().scale_resample.upper()]


def from_cairo(surface: cairo.ImageSurface) -> Image.Image:
  w = surface.get_width()
  h = surface.get_height()
  data = surface.get_data()
  stride = surface.get_stride()
  surface_format = surface.get_format()
  if surface_format == cairo.Format.A1:
    # Format.A1 的转换很慢
    if not data:
      return Image.new("1", (w, h))
    data_w = math.ceil(w / 32) * 32
    im = Image.frombuffer("1", (data_w, h), data.tobytes())
    for x in range(0, w, 8):
      im.paste(im.crop((x, 0, x + 8, h)).transpose(Image.Transpose.FLIP_LEFT_RIGHT), (x, 0))
    return im.crop((0, 0, w, h))
  if surface_format == cairo.Format.A8:
    if not data:
      return Image.new("L", (w, h))
    return Image.frombuffer("L", (w, h), data.tobytes(), "raw", "L", stride, 1)
  if surface_format == cairo.Format.RGB24:
    if not data:
      return Image.new("RGB", (w, h))
    return Image.frombuffer("RGB", (w, h), data.tobytes(), "raw", "BGRX", stride)
  if surface_format == cairo.Format.ARGB32:
    if not data:
      return Image.new("RGBA", (w, h))
    return Image.frombuffer("RGBA", (w, h), data.tobytes(), "raw", "BGRa", stride)
  raise NotImplementedError(f"Unsupported format: {surface_format}")


def to_cairo(im: Image.Image) -> cairo.ImageSurface:
  if im.mode == "1":
    # 1 模式的转换很慢
    w, h = im.size
    data_w = math.ceil(w / 32) * 32
    im = ImageOps.expand(im, (0, 0, data_w - w, 0))
    for x in range(0, data_w, 8):
      im.paste(im.crop((x, 0, x + 8, h)).transpose(Image.Transpose.FLIP_LEFT_RIGHT), (x, 0))
    data = bytearray(im.tobytes())
    return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_A1, w, h)
  if im.mode == "L":
    stride = math.ceil(im.width / 4) * 4
    data = bytearray(im.tobytes("raw", "L", stride))
    return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_A8, im.width, im.height)
  if im.mode == "RGB":
    data = bytearray(im.tobytes("raw", "BGRX"))
    return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_RGB24, im.width, im.height)
  if im.mode == "RGBA":
    data = bytearray(im.tobytes("raw", "BGRa"))
    return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, im.width, im.height)
  raise NotImplementedError(f"Unsupported mode: {im.mode}")


def circle(im: Image.Image, antialias: bool | float = True) -> None:
  ratio = (2 if antialias else 1) if isinstance(antialias, bool) else antialias
  if ratio > 1:
    mask = Image.new("L", (round(im.width * ratio), round(im.height * ratio)))
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, mask.width - 1, mask.height - 1), 255)
    mask = mask.resize(im.size, get_scale_resample())
  else:
    mask = Image.new("L", im.size)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, mask.width - 1, mask.height - 1), 255)
  if "A" in im.getbands():
    mask = ImageChops.multiply(im.getchannel("A"), mask)
  im.putalpha(mask)


def rounded_rectangle(im: Image.Image, radius: int, antialias: bool | float = True) -> None:
  ratio = (2 if antialias else 1) if isinstance(antialias, bool) else antialias
  if ratio > 1:
    circle = Image.new("L", (round(radius * 2 * ratio), round(radius * 2 * ratio)))
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, circle.width - 1, circle.height - 1), 255)
    circle = circle.resize((radius * 2, radius * 2), get_scale_resample())
  else:
    circle = Image.new("L", (radius * 2, radius * 2))
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, circle.width - 1, circle.height - 1), 255)
  mask = Image.new("L", im.size)
  mask.paste(
    circle.crop((0, 0, radius, radius)),
    (0, 0),
  )
  mask.paste(
    circle.crop((radius, 0, radius * 2, radius)),
    (mask.width - radius, 0),
  )
  mask.paste(
    circle.crop((0, radius, radius, radius * 2)),
    (0, mask.height - radius),
  )
  mask.paste(
    circle.crop((radius, radius, radius * 2, radius * 2)),
    (mask.width - radius, mask.height - radius),
  )
  draw = ImageDraw.Draw(mask)
  draw.rectangle((radius, 0, mask.width - radius - 1, radius - 1), 255)
  draw.rectangle((0, radius, mask.width - 1, mask.height - radius - 1), 255)
  draw.rectangle((radius, mask.height - radius, mask.width - radius - 1, mask.height - 1), 255)
  if "A" in im.getbands():
    mask = ImageChops.multiply(im.getchannel("A"), mask)
  im.putalpha(mask)


def center_pad(im: AnyImage, width: int, height: int) -> Image.Image:
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  if im.width > width or im.height > height:
    padded_im = ImageOps.pad(im, (width, height), get_scale_resample())
  else:
    padded_im = Image.new("RGBA", (width, height))
    padded_im.paste(im, ((width - im.width) // 2, (height - im.height) // 2))
  return padded_im


def resize_canvas(im: AnyImage, size: Size, center: Point = (0.5, 0.5)) -> Image.Image:
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  x = size[0] - im.width
  y = size[1] - im.height
  l = int(center[0] * x)
  r = x - l
  t = int(center[1] * y)
  b = y - t
  return ImageOps.expand(im, (t, l, r, b))


def square(im: AnyImage) -> Image.Image:
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  length = min(im.width, im.height)
  x = (im.width - length) // 2
  y = (im.height - length) // 2
  return im.crop((x, y, x + length, y + length))


def contain_down(im: AnyImage, width: int, height: int) -> Image.Image:
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  if im.width > width or im.height > height:
    return ImageOps.contain(im, (width, height), get_scale_resample())
  return im


def resize_width(im: AnyImage, width: int) -> Image.Image:
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  return ImageOps.contain(im, (width, 99999), get_scale_resample())


def resize_height(im: AnyImage, height: int) -> Image.Image:
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  return ImageOps.contain(im, (99999, height), get_scale_resample())


def background(im: AnyImage, bg: Color = (255, 255, 255)) -> Image.Image:
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  if im.mode == "P":
    assert im.palette
    if "A" in im.palette.mode:
      im = im.convert(im.palette.mode)
  if "A" in im.getbands():
    bg = color.split_rgb(bg) if isinstance(bg, int) else bg
    result = Image.new("RGB", im.size, bg)
    result.paste(im, mask=im.getchannel("A"))
    return result
  return im.convert("RGB")


def frames(im: Image.Image) -> Generator[Image.Image, None, None]:
  if not getattr(im, "is_animated", False):
    yield im
    return
  yield from ImageSequence.Iterator(im)


def sample_frames(im: Image.Image, frametime: int) -> Generator[Image.Image, None, None]:
  if not getattr(im, "is_animated", False):
    while True:
      yield im
  n_frames = getattr(im, "n_frames", 1)
  main_pos = 0
  sample_pos = 0
  i = 0
  while True:
    duration = im.info["duration"]
    while sample_pos <= main_pos < sample_pos + duration:
      yield im
      main_pos += frametime
    sample_pos += duration
    i += 1
    if i == n_frames:
      i = 0
    im.seek(i)


def paste(
  dst: Image.Image,
  src: AnyImage | PasteColor,
  xy: Point = (0, 0),
  anchor: Anchor = "lt",
) -> None:
  if isinstance(src, cairo.ImageSurface):
    paste_src = from_cairo(src)
    width, height = paste_src.size
  elif isinstance(src, Image.Image):
    paste_src = src
    width, height = paste_src.size
  else:
    paste_src, (width, height) = src
    paste_src = color.split_rgb(paste_src) if isinstance(paste_src, int) else paste_src
  x1, y1 = xy
  xa, ya = anchor
  if xa == "m":
    x1 -= width / 2
  elif xa == "r":
    x1 -= width
  if ya == "m":
    y1 -= height / 2
  elif ya == "b":
    y1 -= height
  x1 = round(x1)
  y1 = round(y1)
  if (
    dst.mode in ("RGBA", "LA")
    and isinstance(paste_src, Image.Image)
    and paste_src.has_transparency_data
  ):
    if paste_src.mode != dst.mode:
      paste_src = paste_src.convert(dst.mode)
    dst.alpha_composite(paste_src, (x1, y1))
  else:
    paste_mask = None
    if isinstance(paste_src, Image.Image):
      if "transparency" in paste_src.info:
        paste_src = paste_src.copy()
        paste_src.apply_transparency()
      if paste_src.palette and paste_src.palette.mode.endswith("A"):
        paste_src = paste_src.convert(paste_src.palette.mode)
        paste_mask = paste_src
      elif paste_src.mode.endswith(("A", "a")):
        paste_mask = paste_src
    dst.paste(paste_src, (x1, y1), paste_mask)


def replace(
  dst: Image.Image,
  src: AnyImage | PasteColor,
  xy: Point = (0, 0),
  anchor: Anchor = "lt",
) -> None:
  if isinstance(src, cairo.ImageSurface):
    paste_src = from_cairo(src)
    width, height = paste_src.size
  elif isinstance(src, Image.Image):
    paste_src = src
    width, height = paste_src.size
  else:
    paste_src, (width, height) = src
    paste_src = color.split_rgb(paste_src) if isinstance(paste_src, int) else paste_src
  x1, y1 = xy
  xa, ya = anchor
  if xa == "m":
    x1 -= width / 2
  elif xa == "r":
    x1 -= width
  if ya == "m":
    y1 -= height / 2
  elif ya == "b":
    y1 -= height
  x1 = round(x1)
  y1 = round(y1)
  dst.paste(paste_src, (x1, y1))


def flatten(im: Image.Image, bg: color.RGB = (255, 255, 255)) -> Image.Image:
  out_im = Image.new("RGB", im.size, bg)
  out_im.paste(im, mask=im)
  return out_im


def _check_libimagequant() -> bool:
  global _libimagequant_available, _libimagequant_warned
  if _libimagequant_available is None:
    _libimagequant_available = cast(bool, features.check("libimagequant"))
  if not _libimagequant_available and not _libimagequant_warned:
    logger.warning(
      "已启用 libimagequant，但没有安装 libimagequant 或者 Pillow 没有编译 libimagequant 支持，"
      "请参考 Pillow 和 IdhagnBot 的文档获取帮助。这条警告只会出现一次。",
    )
    _libimagequant_warned = True
  return _libimagequant_available


def quantize(im: AnyImage) -> Image.Image:
  config = CONFIG()
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  if config.libimagequant is True and _check_libimagequant():
    # Image.new 在 RGB 模式下不带 color 参数会给隐藏的 Alpha 通道填充 0 而非 255
    # 也就是颜色实际上是 (0, 0, 0, 0) 而非 (0, 0, 0, 255)
    # 这会导致 libimagequant 产生的图片变绿（新版 libimagequant 似乎已经修复了这个问题）
    # 所以要么给所有的 Image.new 都显式加上 (0, 0, 0) 作为 color 参数
    # 要么 quantize 前先转换成 RGBA
    p = im.quantize(method=Image.Quantize.LIBIMAGEQUANT)
    assert p.palette
    if p.palette.mode != "RGBA":
      return p
    for i in range(0, len(p.palette.palette), 4):
      if p.palette.palette[i + 3] == 0:
        p.info["transparency"] = i // 4
        break
    return p
  method = Image.Quantize[config.quantize.upper()]
  if im.mode == "RGBA":
    # RGBA 图片的 quantize 方法不能用 palette 参数，使用内部 API 强行量化有奇怪的问题
    # 我们手搓一个
    a = ImageChops.invert(im.getchannel("A").convert("1"))
    rgb = flatten(im)
    if config.dither:
      palette = rgb.quantize(255, method=method)
      p = rgb.quantize(method=method, palette=palette)
    else:
      p = rgb.quantize(255, method=method, dither=Image.Dither.NONE)
    assert p.palette
    palette_data = p.palette.tobytes()
    pos = len(palette_data) // 3
    p.palette.palette = palette_data + b"\0\0\0"
    p.info["transparency"] = pos
    p.paste(pos, mask=a)
    return p
  # 必须要量化两次才有抖动仿色（除非用 libimagequant）
  # 参见 https://github.com/python-pillow/Pillow/issues/5836
  palette = im.quantize(method=method)
  if not config.dither:
    return palette
  return im.quantize(method=method, palette=palette)


class RemapTransform:
  def __init__(self, old_size: Size, new_plane: Plane, old_plane: Plane | None = None) -> None:
    widths = [point[0] for point in new_plane]
    heights = [point[1] for point in new_plane]
    self.old_size = old_size
    self.new_size = (math.ceil(max(widths)), math.ceil(max(heights)))
    if old_plane is None:
      old_plane = ((0, 0), (old_size[0], 0), (old_size[0], old_size[1]), (0, old_size[1]))
    self.data = self._find_coefficients(old_plane, new_plane)

  def getdata(self) -> tuple[int, PerspectiveData]:
    return Image.Transform.PERSPECTIVE, self.data

  @staticmethod
  def _find_coefficients(old_plane: Plane, new_plane: Plane) -> PerspectiveData:
    import numpy as np

    matrix: list[list[float]] = []
    for p1, p2 in zip(old_plane, new_plane, strict=True):
      matrix.append([p2[0], p2[1], 1, 0, 0, 0, -p1[0] * p2[0], -p1[0] * p2[1]])
      matrix.append([0, 0, 0, p2[0], p2[1], 1, -p1[1] * p2[0], -p1[1] * p2[1]])
    a = np.array(matrix)
    b = np.array(old_plane).reshape(8)
    res_ = np.linalg.inv(a.T @ a) @ a.T @ b
    return cast(PerspectiveData, tuple(res_))


class PixelAccess(Protocol[T]):
  def __setitem__(self, xy: tuple[int, int], color: T, /) -> None: ...
  def __getitem__(self, xy: tuple[int, int], /) -> T: ...
  def putpixel(self, xy: tuple[int, int], color: T, /) -> None: ...
  def getpixel(self, xy: tuple[int, int], /) -> T: ...


def load(im: Image.Image, _type: type[T]) -> PixelAccess[T]:
  return cast(PixelAccess[T], im.load())


async def open_url(url: str) -> Image.Image:
  if url.startswith("file://"):
    path = path_from_url(url)
    return await run_sync(lambda: Image.open(path))
  async with get_session().get(url) as response:
    data = await response.read()
    return await run_sync(lambda: Image.open(BytesIO(data)))


def colorize(
  image: AnyImage,
  black: str | int | tuple[int, ...],
  white: str | int | tuple[int, ...],
  mid: str | int | tuple[int, ...] | None = None,
  blackpoint: int = 0,
  whitepoint: int = 255,
  midpoint: int = 127,
) -> Image.Image:
  # ImageOps.colorize 的参数 black、white、mid 类型缺失 Tuple[int, ...]
  return ImageOps.colorize(
    from_cairo(image) if isinstance(image, cairo.ImageSurface) else image,
    cast(Any, black),
    cast(Any, white),
    cast(Any, mid),
    blackpoint,
    whitepoint,
    midpoint,
  )


@overload
def to_segment(im: AnyImage, *, fmt: str = ..., **kw: Any) -> ImageSeg: ...


@overload
def to_segment(
  im: Sequence[AnyImage],
  duration: list[int] | int | Image.Image,
  *,
  fmt: str = ...,
  afmt: str = ...,
  **kw: Any,
) -> ImageSeg: ...


def to_segment(
  im: AnyImage | Sequence[AnyImage],
  duration: list[int] | int | Image.Image = 0,
  *,
  fmt: str = "png",
  afmt: str = "gif",
  **kw: Any,
) -> ImageSeg:
  f = BytesIO()
  if isinstance(im, Sequence):
    if len(im) > 1:
      if isinstance(duration, Image.Image):
        duration = [im.info["duration"] for im in ImageSequence.Iterator(duration)]
      if isinstance(duration, list) and len(duration) != len(im):
        raise ValueError("Duration list length doesn't match frames count.")
      frames = [from_cairo(x) if isinstance(x, cairo.ImageSurface) else x for x in im]
      afmt = afmt.lower()
      if afmt == "gif":
        frames = [x if x.mode == "P" else quantize(x) for x in frames]
        # 只对透明图片使用 disposal，防止不透明图片有鬼影
        disposal = 2 if any("transparency" in x.info for x in frames) else 0
        frames[0].save(
          f,
          "GIF",
          append_images=frames[1:],
          save_all=True,
          loop=0,
          disposal=disposal,
          duration=duration,
          **kw,
        )
      else:
        frames[0].save(f, afmt, append_images=frames[1:], duration=duration)
      return ImageSeg(raw=f, name=f"image.{afmt}")
    im = im[0]
  fmt = fmt.lower()
  if isinstance(im, cairo.ImageSurface):
    if fmt == "png":
      im.write_to_png(f)
      return ImageSeg(raw=f)
    im = from_cairo(im)
  im.save(f, fmt, **kw)
  return ImageSeg(raw=f, name=f"image.{fmt}")
