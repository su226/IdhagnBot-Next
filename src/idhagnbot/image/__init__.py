import math
from collections.abc import Generator, Sequence
from io import BytesIO
from typing import (
  Any,
  Literal,
  Optional,
  Protocol,
  TypeVar,
  Union,
  cast,
  overload,
)

import cairo
import nonebot
from nonebot import logger
from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageSequence, features
from pydantic import BaseModel

from idhagnbot import color
from idhagnbot.config import SharedConfig

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
  "frames",
  "from_cairo",
  "load",
  "paste",
  "quantize",
  "resize_canvas",
  "resize_height",
  "resize_width",
  "sample_frames",
  "to_segment",
]


Resample = Literal["nearest", "bilinear", "bicubic"]
ScaleResample = Union[Resample, Literal["box", "hamming", "lanczos"]]
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
Color = Union[color.RGB, int]
Plane = tuple[Point, Point, Point, Point]
PerspectiveData = tuple[float, float, float, float, float, float, float, float]
PasteColor = tuple[Color, Size]
AnyImage = Union[Image.Image, cairo.ImageSurface]
T = TypeVar("T")
_libimagequant_available: Optional[bool] = None
_libimagequant_warned: bool = False


def get_resample() -> Image.Resampling:
  return Image.Resampling[CONFIG().resample.upper()]


def get_scale_resample() -> Image.Resampling:
  return Image.Resampling[CONFIG().scale_resample.upper()]


def from_cairo(surface: cairo.ImageSurface) -> Image.Image:
  w = surface.get_width()
  h = surface.get_height()
  data = surface.get_data()
  surface_format = surface.get_format()
  if surface_format == cairo.Format.A1:
    if not data:
      return Image.new("1", (w, h))
    data_w = math.ceil(w / 32) * 32
    im = Image.frombytes("1", (data_w, h), bytes(data))
    for x in range(0, w, 8):
      im.paste(im.crop((x, 0, x + 8, h)).transpose(Image.Transpose.FLIP_LEFT_RIGHT), (x, 0))
    return im.crop((0, 0, w, h))
  if surface_format == cairo.Format.A8:
    if not data:
      return Image.new("L", (w, h))
    data_w = math.ceil(w / 4) * 4
    return Image.frombytes("L", (data_w, h), bytes(data)).crop((0, 0, w, h))
  if surface_format == cairo.Format.RGB24:
    if not data:
      return Image.new("RGB", (w, h))
    b, g, r, _ = Image.frombytes("RGBX", (w, h), bytes(data)).split()
    return Image.merge("RGB", (r, g, b))
  if surface_format == cairo.Format.ARGB32:
    if not data:
      return Image.new("RGBA", (w, h))
    b, g, r, a = Image.frombytes("RGBa", (w, h), bytes(data)).convert("RGBA").split()
    return Image.merge("RGBA", (r, g, b, a))  # BGRa -> BGRA -> RGBA
  raise NotImplementedError(f"Unsupported format: {surface_format}")


def to_cairo(im: Image.Image) -> cairo.ImageSurface:
  im = im.convert("RGBA").convert("RGBa")  # 不能由 RGB 直接转换为 RGBa
  r, g, b, a = im.split()
  data = memoryview(bytearray(Image.merge("RGBa", (b, g, r, a)).tobytes()))
  return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, im.width, im.height)


def circle(im: Image.Image, antialias: Union[bool, float] = True) -> None:
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


def rounded_rectangle(
  im: Image.Image,
  radius: int,
  antialias: Union[bool, float] = True,
) -> None:
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
  src: Union[AnyImage, PasteColor],
  xy: Point = (0, 0),
  mask: Union[AnyImage, None] = None,
  anchor: Anchor = "lt",
) -> None:
  if isinstance(mask, cairo.ImageSurface):
    mask = from_cairo(mask)
  if isinstance(src, cairo.ImageSurface):
    src = from_cairo(src)
  if isinstance(src, Image.Image):
    if src.mode == "P":
      assert src.palette
      if "A" in src.palette.mode:
        src = src.convert(src.palette.mode)  # RGBA (也可能是LA？)
    if "A" in src.getbands():
      mask = ImageChops.multiply(mask, src.getchannel("A")) if mask else src.getchannel("A")
    paste_src = src
    width, height = src.size
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
  x2 = x1 + width
  y2 = y1 + height
  dst.paste(paste_src, (x1, y1, x2, y2), mask)


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


def _add_transparency(im: Image.Image) -> None:
  assert im.palette
  if im.palette.mode != "RGBA":
    return
  for i in range(0, len(im.palette.palette), 4):
    if im.palette.palette[i + 3] == 0:
      im.info["transparency"] = i // 4
      break


def quantize(im: AnyImage, palette: Optional[Image.Image] = None) -> Image.Image:
  config = CONFIG()
  im = from_cairo(im) if isinstance(im, cairo.ImageSurface) else im
  if config.libimagequant is True and _check_libimagequant():
    # Image.new 在 RGB 模式下不带 color 参数会给隐藏的 Alpha 通道填充 0 而非 255
    # 也就是颜色实际上是 (0, 0, 0, 0) 而非 (0, 0, 0, 255)
    # 这会导致 libimagequant 产生的图片变绿
    # 所以要么给所有的 Image.new 都显式加上 (0, 0, 0) 作为 color 参数
    # 要么 quantize 前先转换成 RGBA
    im = im.convert("RGBA").quantize(method=Image.Quantize.LIBIMAGEQUANT, palette=palette)
    _add_transparency(im)
    return im
  if im.mode == "RGBA":
    method = Image.Quantize.FASTOCTREE
  else:
    method = Image.Quantize[config.quantize.upper()]
  # 必须要量化两次才有抖动仿色（除非用 libimagequant）
  # 参见 https://github.com/python-pillow/Pillow/issues/5836
  if not palette:
    palette = im.quantize(method=method)
    if not config.dither:
      _add_transparency(palette)
      return palette
  # HACK: RGBA 图片的 quantize 方法不能用 palette 参数，因此只能使用 Pillow 的内部 API
  im = cast(
    Image.Image,
    cast(Any, palette)._new(im.im.convert("P", Image.Dither.FLOYDSTEINBERG, palette.im)),
  )
  _add_transparency(im)
  return im


class RemapTransform:
  def __init__(self, old_size: Size, new_plane: Plane, old_plane: Optional[Plane] = None) -> None:
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
    for p1, p2 in zip(old_plane, new_plane):
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


def colorize(
  image: AnyImage,
  black: Union[str, int, tuple[int, ...]],
  white: Union[str, int, tuple[int, ...]],
  mid: Union[str, int, tuple[int, ...], None] = None,
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
  duration: Union[list[int], int, Image.Image],
  *,
  afmt: str = ...,
  **kw: Any,
) -> ImageSeg: ...


def to_segment(
  im: Union[AnyImage, Sequence[AnyImage]],
  duration: Union[list[int], int, Image.Image] = 0,
  *,
  fmt: str = "png",
  afmt: str = "gif",
  **kw: Any,
) -> ImageSeg:
  f = BytesIO()
  if isinstance(im, cairo.ImageSurface):
    if fmt == "png":
      im.write_to_png(f)
      return ImageSeg(raw=f)
    im = from_cairo(im)
  if isinstance(im, Sequence):
    frames = [from_cairo(x) if isinstance(x, cairo.ImageSurface) else x for x in im]
    if len(frames) > 1:
      if isinstance(duration, Image.Image):
        duration = [im.info["duration"] for im in ImageSequence.Iterator(duration)]
      if isinstance(duration, list) and len(duration) != len(im):
        raise ValueError("Duration list length doesn't match frames count.")
      if afmt.lower() == "gif":
        frames = [x if x.mode == "P" else quantize(x) for x in frames]
        # 只对透明图片使用 disposal，防止不透明图片有鬼影
        disposal = 2 if any("transparency" in x.info for x in frames) else 0
        frames[0].save(
          f,
          "GIF",
          append_images=im[1:],
          save_all=True,
          loop=0,
          disposal=disposal,
          duration=duration,
          **kw,
        )
      return ImageSeg(raw=f)
    im = frames[0]
  im.save(f, fmt, **kw)
  return ImageSeg(raw=f)
