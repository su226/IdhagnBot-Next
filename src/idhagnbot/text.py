import math
from typing import Any, Literal, TypeAlias, Union, cast, overload

import cairo
import gi
from PIL import Image
from pydantic import BaseModel, Field
from typing_extensions import Self

from idhagnbot import image
from idhagnbot.color import split_rgb
from idhagnbot.config import SharedConfig

gi.require_version("GLib", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import GLib, Pango, PangoCairo

CairoAntialias = Literal["default", "none", "fast", "good", "best", "gray", "subpixel"]
CairoSubpixel = Literal["default", "rgb", "bgr", "vrgb", "vbgr"]
CairoHintMetrics = Literal["default", False, True]
CairoHintStyle = Literal["default", "none", "slight", "medium", "full"]


class Config(BaseModel):
  special_font: dict[str, str] = Field(default_factory=dict)
  font_substitute: dict[str, str] = Field(default_factory=dict)
  text_antialias: CairoAntialias = "gray"
  text_subpixel: CairoSubpixel = "default"
  text_hint_metrics: CairoHintMetrics = True
  text_hint_style: CairoHintStyle = "slight"


CONFIG = SharedConfig("text", Config)
Layout: TypeAlias = Pango.Layout
Wrap = Literal["word", "char", "word_char"]
Ellipsize = Literal["start", "middle", "end"] | None
Align = Literal["l", "m", "r"]
ImageAlign = Literal["top", "middle", "baseline", "bottom"]
WRAPS: dict[Wrap, Pango.WrapMode] = {
  "word": Pango.WrapMode.WORD,
  "char": Pango.WrapMode.CHAR,
  "word_char": Pango.WrapMode.WORD_CHAR,
}
ELLIPSIZES: dict[Ellipsize, Pango.EllipsizeMode] = {
  None: Pango.EllipsizeMode.NONE,
  "start": Pango.EllipsizeMode.START,
  "middle": Pango.EllipsizeMode.MIDDLE,
  "end": Pango.EllipsizeMode.END,
}
ALIGNS: dict[Align, Pango.Alignment] = {
  "l": Pango.Alignment.LEFT,
  "m": Pango.Alignment.CENTER,
  "r": Pango.Alignment.RIGHT,
}
ANTIALIASES: dict[CairoAntialias, cairo.Antialias] = {
  "default": cairo.Antialias.DEFAULT,
  "none": cairo.Antialias.NONE,
  "fast": cairo.Antialias.FAST,
  "good": cairo.Antialias.GOOD,
  "best": cairo.Antialias.BEST,
  "gray": cairo.Antialias.GRAY,
  "subpixel": cairo.Antialias.SUBPIXEL,
}
SUBPIXEL_ORDERS: dict[CairoSubpixel, cairo.SubpixelOrder] = {
  "default": cairo.SubpixelOrder.DEFAULT,
  "rgb": cairo.SubpixelOrder.RGB,
  "bgr": cairo.SubpixelOrder.BGR,
  "vrgb": cairo.SubpixelOrder.VRGB,
  "vbgr": cairo.SubpixelOrder.VBGR,
}
HINT_METRICS: dict[CairoHintMetrics, cairo.HintMetrics] = {
  "default": cairo.HintMetrics.DEFAULT,
  False: cairo.HintMetrics.OFF,
  True: cairo.HintMetrics.ON,
}
HINT_STYLES: dict[CairoHintStyle, cairo.HintStyle] = {
  "default": cairo.HintStyle.DEFAULT,
  "none": cairo.HintStyle.NONE,
  "slight": cairo.HintStyle.SLIGHT,
  "medium": cairo.HintStyle.MEDIUM,
  "full": cairo.HintStyle.FULL,
}


# 增加一个辅助类，防止 Pango.Context 和 RichText 循环引用导致内存泄漏
class ImageHolder:
  def __init__(self) -> None:
    self._images = dict[int, cairo.ImageSurface]()

  def _render_images(self, cr: "cairo.Context[Any]", attr: Pango.AttrShape, do_path: bool) -> None:
    if do_path:
      return
    x, y = cr.get_current_point()
    y += attr.ink_rect.y / Pango.SCALE
    surface = self._images[cast(Any, attr.data)]
    cr.set_source_surface(surface, x, y)
    cr.rectangle(x, y, surface.get_width(), surface.get_height())
    cr.fill()

  def bind(self, context: Pango.Context) -> None:
    PangoCairo.context_set_shape_renderer(context, self._render_images)

  def __contains__(self, id: int) -> bool:
    return id in self._images

  def __setitem__(self, id: int, image: cairo.ImageSurface) -> None:
    self._images[id] = image


class RichText:
  _IMAGE_REPLACEMENT = "￼".encode()

  def __init__(self) -> None:
    self._context = Pango.Context()
    self._context.set_font_map(PangoCairo.FontMap.get_default())
    self._images = ImageHolder()
    font_options(self._context)
    self._images.bind(self._context)
    self._utf8 = bytearray()
    self._attrs = Pango.AttrList()
    self._layout = Layout.new(self._context)

  def append(self, text: str) -> Self:
    text = text.replace("\r", "").replace("\n", "\u2028")
    self._utf8.extend(text.encode())
    return self

  def append_markup(self, markup: str) -> Self:
    markup = markup.replace("\r", "").replace("\n", "\u2028")
    _, attrs, text, _ = Pango.parse_markup(markup, -1, "\0")
    utf8 = text.encode()
    self._attrs.splice(attrs, len(self._utf8), len(utf8))
    self._utf8.extend(utf8)
    return self

  def append_image(self, im: Image.Image, align: ImageAlign = "middle") -> Self:
    image_id = id(im)
    if image_id not in self._images:
      self._images[image_id] = image.to_cairo(im)
    metrics = self._context.get_metrics(self._layout.get_font_description())
    rect = Pango.Rectangle()
    if align == "top":
      rect.y = -metrics.get_ascent()
    elif align == "middle":
      rect.y = (metrics.get_descent() - metrics.get_ascent() - im.height * Pango.SCALE) // 2
    elif align == "bottom":
      rect.y = -im.height * Pango.SCALE + metrics.get_descent()
    else:
      rect.y = -im.height * Pango.SCALE
    rect.width = im.width * Pango.SCALE
    rect.height = im.height * Pango.SCALE
    attr = Pango.AttrShape.new_with_data(rect, rect, cast(Any, image_id))
    attr.start_index = len(self._utf8)
    attr.end_index = len(self._utf8) + len(self._IMAGE_REPLACEMENT)
    self._utf8.extend(self._IMAGE_REPLACEMENT)
    self._attrs.insert(attr)
    return self

  def set_font(self, font: str, size: float) -> Self:
    if value := CONFIG().font_substitute.get(font, None):
      font = value
    desc = Pango.FontDescription.from_string(font)
    desc.set_absolute_size(Pango.SCALE * size)
    self._layout.set_font_description(desc)
    return self

  def set_width(self, width: int) -> Self:
    self._layout.set_width(width * Pango.SCALE)
    return self

  def set_height(self, height: int) -> Self:
    if height > 0:
      height *= Pango.SCALE
    self._layout.set_height(height)
    return self

  def set_wrap(self, wrap: Wrap) -> Self:
    self._layout.set_wrap(WRAPS[wrap])
    return self

  def set_ellipsize(self, ellipsize: Ellipsize) -> Self:
    self._layout.set_ellipsize(ELLIPSIZES[ellipsize])
    return self

  def set_spacing(self, spacing: float) -> Self:
    if spacing < 0:
      self._layout.set_line_spacing(spacing)
      self._layout.set_spacing(0)
    else:
      self._layout.set_line_spacing(0)
      self._layout.set_spacing(int(spacing * Pango.SCALE))
    return self

  def set_align(self, align: Align) -> Self:
    self._layout.set_alignment(ALIGNS[align])
    return self

  def size(self) -> tuple[int, int]:
    _, rect = self._layout.get_pixel_extents()
    return (rect.width, rect.height)

  def unwrap(self) -> Layout:
    self._layout.set_text(self._utf8.decode())
    self._layout.set_attributes(self._attrs)
    return self._layout

  def render(
    self,
    color: image.Color = (0, 0, 0),
    stroke: float = 0,
    stroke_color: image.Color = (255, 255, 255),
  ) -> Image.Image:
    return render(self.unwrap(), color=color, stroke=stroke, stroke_color=stroke_color)

  def paste(
    self,
    im: Image.Image,
    xy: tuple[float, float],
    anchor: image.Anchor = "lt",
    color: image.Color = (0, 0, 0),
    stroke: float = 0,
    stroke_color: image.Color = (255, 255, 255),
  ) -> Image.Image:
    src = render(self.unwrap(), color=color, stroke=stroke, stroke_color=stroke_color)
    image.paste(im, src, xy, anchor=anchor)
    return src


def escape(text: str) -> str:
  return GLib.markup_escape_text(text, -1)


def special_font(name: str, fallback: str) -> str:
  if value := CONFIG().special_font.get(name, None):
    return value
  return fallback


def font_options(
  context: Union[None, Pango.Context, "cairo.Context[Any]"] = None,
) -> cairo.FontOptions:
  config = CONFIG()
  options = cairo.FontOptions()
  options.set_antialias(ANTIALIASES[config.text_antialias])
  options.set_subpixel_order(SUBPIXEL_ORDERS[config.text_subpixel])
  options.set_hint_metrics(HINT_METRICS[config.text_hint_metrics])
  options.set_hint_style(HINT_STYLES[config.text_hint_style])
  if isinstance(context, Pango.Context):
    PangoCairo.context_set_font_options(context, options)
  elif isinstance(context, cairo.Context):
    context.set_font_options(options)
  return options


def layout(
  content: str,
  font: str,
  size: float,
  *,
  box: int | None = None,
  wrap: Wrap = "word",
  ellipsize: Ellipsize = None,
  markup: bool = False,
  align: Align = "l",
  spacing: int = 0,
  lines: int = 0,
) -> Layout:
  render = RichText().set_font(font, size).set_wrap(wrap).set_align(align).set_spacing(spacing)
  if box:
    render.set_width(box)
  if lines:
    render.set_height(-lines).set_ellipsize(ellipsize)
  if markup:
    try:
      render.append_markup(content)
    except GLib.Error:
      render.append(content)
  else:
    render.append(content)
  return render.unwrap()


@overload
def render(
  content: Layout,
  *,
  color: image.Color = ...,
  stroke: float = ...,
  stroke_color: image.Color = ...,
) -> Image.Image: ...
@overload
def render(
  content: str,
  font: str,
  size: float,
  *,
  color: image.Color = ...,
  stroke: float = ...,
  stroke_color: image.Color = ...,
  box: int | None = ...,
  wrap: Wrap = ...,
  ellipsize: Ellipsize = ...,
  markup: bool = ...,
  align: Align = ...,
  spacing: int = ...,
  lines: int = ...,
) -> Image.Image: ...
def render(
  content: str | Layout,
  *args: Any,
  color: image.Color = (0, 0, 0),
  stroke: float = 0,
  stroke_color: image.Color = (255, 255, 255),
  **kw: Any,
) -> Image.Image:
  l = content if isinstance(content, Layout) else layout(content, *args, **kw)
  _, rect = l.get_pixel_extents()
  margin = math.ceil(stroke)
  x = -rect.x + margin
  y = -rect.y + margin
  w = rect.width + margin * 2
  h = rect.height + margin * 2
  with cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h) as surface:
    cr = cairo.Context(surface)
    if stroke:
      if isinstance(stroke_color, int):
        stroke_color = split_rgb(stroke_color)
      cr.move_to(x, y)
      PangoCairo.layout_path(cr, l)
      cr.set_line_width(stroke * 2)
      cr.set_source_rgb(stroke_color[0] / 255, stroke_color[1] / 255, stroke_color[2] / 255)
      cr.stroke()
    if isinstance(color, int):
      color = split_rgb(color)
    cr.move_to(x, y)
    cr.set_source_rgb(color[0] / 255, color[1] / 255, color[2] / 255)
    PangoCairo.show_layout(cr, l)
    return image.from_cairo(surface)


@overload
def paste(
  im: Image.Image,
  xy: tuple[float, float],
  content: Layout,
  *,
  anchor: image.Anchor = ...,
  color: image.Color = ...,
  stroke: float = ...,
  stroke_color: image.Color = ...,
) -> Image.Image: ...
@overload
def paste(
  im: Image.Image,
  xy: tuple[float, float],
  content: str,
  font: str,
  size: float,
  *,
  anchor: image.Anchor = ...,
  color: image.Color = ...,
  stroke: float = ...,
  stroke_color: image.Color = ...,
  box: int | None = ...,
  wrap: Wrap = ...,
  ellipsize: Ellipsize = ...,
  markup: bool = ...,
  align: Align = ...,
  spacing: int = ...,
  lines: int = ...,
) -> Image.Image: ...
def paste(
  im: Image.Image,
  xy: tuple[float, float],
  *args: Any,
  anchor: image.Anchor = "lt",
  **kw: Any,
) -> Image.Image:
  text = render(*args, **kw)
  image.paste(im, text, xy, anchor=anchor)
  return text
