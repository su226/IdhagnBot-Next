import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import KW_ONLY, dataclass
from itertools import count
from typing import SupportsIndex, overload

from PIL import Image

from idhagnbot.color import RGB, split_rgb
from idhagnbot.image import paste, resize_height, resize_width
from idhagnbot.material_color import source_color_from_image
from idhagnbot.material_color.hct import Hct
from idhagnbot.text import paste as paste_text
from idhagnbot.text import render


@dataclass(frozen=True)
class Palette:
  bg: RGB
  fg: RGB
  text: RGB


DEFAULT_PALETTE = Palette((224, 224, 224), (192, 192, 192), (0, 0, 0))


def make_material_palette(
  hue: float,
  chroma: float,
  tone_bg: float = 95,
  tone_fg: float = 70,
  tone_text: float = 40,
) -> Palette:
  return Palette(
    bg=split_rgb(int(Hct(hue, chroma, tone_bg))),
    fg=split_rgb(int(Hct(hue, chroma, tone_fg))),
    text=split_rgb(int(Hct(hue, chroma, tone_text))),
  )


def material_palette_from_icon(
  icon: Image.Image,
  min_chroma: float = 48,
  tone_bg: float = 95,
  tone_fg: float = 70,
  tone_text: float = 40,
) -> Palette:
  hct = Hct.from_argb(source_color_from_image(icon))
  return make_material_palette(
    hct.hue,
    max(min_chroma, hct.chroma),
    tone_bg=tone_bg,
    tone_fg=tone_fg,
    tone_text=tone_text,
  )


Pattern = Callable[[int], Palette]


def pattern_full(palette: Palette) -> Pattern:
  return lambda i: palette


def pattern_stripe(even: Palette, odd: Palette) -> Pattern:
  return lambda i: even if i & 1 == 0 else odd


DEFAULT_STRIPE_PATTERN = pattern_stripe(
  DEFAULT_PALETTE,
  Palette((232, 232, 232), (200, 200, 200), (0, 0, 0)),
)


def material_pattern_stripe_from_icon(
  icon: Image.Image,
  min_chroma: float = 48,
  tone_bg: float = 95,
  tone_bg2: float = 93,
  tone_fg: float = 70,
  tone_fg2: float = 68,
  tone_text: float = 40,
) -> Pattern:
  hct = Hct.from_argb(source_color_from_image(icon))
  chroma = max(min_chroma, hct.chroma)
  color_text = split_rgb(int(Hct(hct.hue, chroma, tone_text)))
  return pattern_stripe(
    Palette(
      bg=split_rgb(int(Hct(hct.hue, chroma, tone_bg))),
      fg=split_rgb(int(Hct(hct.hue, chroma, tone_fg))),
      text=color_text,
    ),
    Palette(
      bg=split_rgb(int(Hct(hct.hue, chroma, tone_bg2))),
      fg=split_rgb(int(Hct(hct.hue, chroma, tone_fg2))),
      text=color_text,
    ),
  )


@dataclass(frozen=True)
class Item:
  value: float
  _: KW_ONLY
  name: str = ""
  icon: Image.Image | None = None
  palette: Palette | None = None


@dataclass(frozen=True)
class _RenderItem:
  value: float
  _: KW_ONLY
  name: str
  icon: Image.Image | None
  palette: Palette


# by ChatGPT
def get_nice_max(max_value: float, max_split: int) -> tuple[float, float]:
  if max_value == 0:
    return 1, 1

  raw = max_value / max_split

  exponent = math.floor(math.log10(raw))
  fraction = raw / math.pow(10, exponent)

  if fraction <= 1:
    nice_fraction = 1
  elif fraction <= 2:
    nice_fraction = 2
  elif fraction <= 5:
    nice_fraction = 5
  else:
    nice_fraction = 10

  interval = nice_fraction * math.pow(10, exponent)

  return math.ceil(max_value / interval) * interval, interval


def display_split(line: float, digits: int = 1) -> str:
  digits = math.floor(math.log10(line))
  if digits > 5 or digits < -4:
    mantissa = round(line / math.pow(10, digits), digits)
    mantissa_i = int(mantissa)
    if mantissa == mantissa_i:
      return f"{mantissa_i}e{digits}"
    return f"{mantissa}e{digits}"
  rounded = round(line, -digits + digits)
  rounded_i = int(rounded)
  if rounded == rounded_i:
    return str(rounded_i)
  return str(rounded)


class BaseBarChart(list[Item]):
  def __init__(self, items: Sequence[float | Item] = ()) -> None:
    super().__init__(item if isinstance(item, Item) else Item(item) for item in items)
    self.bar_width = 64
    self.pattern = pattern_full(DEFAULT_PALETTE)
    self.background_color = (255, 255, 255)
    self.line_color = (0, 0, 0, 31)
    self.font_size = 32
    self.max_split = 10
    self.integral_splits = False
    self.title = ""
    self.show_values = True

  @overload
  def __setitem__(self, i: SupportsIndex, item: float | Item, /) -> None: ...

  @overload
  def __setitem__(
    self,
    i: "slice[SupportsIndex | None]",
    items: Iterable[float | Item],
    /,
  ) -> None: ...

  def __setitem__(
    self,
    i: "SupportsIndex | slice[SupportsIndex | None]",
    item_or_items: float | Item | Iterable[float | Item],
    /,
  ) -> None:
    if isinstance(i, slice) and not isinstance(item_or_items, int | float | Item):
      items = item_or_items
      super().__setitem__(i, (item if isinstance(item, Item) else Item(item) for item in items))
    elif not isinstance(i, slice) and isinstance(item_or_items, int | float | Item):
      item = item_or_items
      super().__setitem__(i, item if isinstance(item, Item) else Item(item))
    else:
      raise TypeError

  def append(self, item: float | Item, /) -> None:
    super().append(item if isinstance(item, Item) else Item(item))

  def extend(self, items: Iterable[float | Item], /) -> None:
    super().extend(item if isinstance(item, Item) else Item(item) for item in items)

  def insert(self, i: SupportsIndex, item: float | Item, /) -> None:
    super().insert(i, item if isinstance(item, Item) else Item(item))

  def _calc_splits(self) -> tuple[float, list[tuple[float, Image.Image]]]:
    max_value = max(item.value for item in self)
    split_max, split_unit = get_nice_max(max_value, self.max_split)
    if self.integral_splits:
      split_max = math.ceil(split_max)
      split_unit = math.ceil(split_unit)
    splits = list[tuple[float, Image.Image]]()
    # 让 line_max 稍微变大一点以防止浮点误差的影响，不知道是否有必要
    split_max = split_max + 0.1 * split_unit
    for i in count(1):
      split = i * split_unit
      if split > split_max:
        break
      splits.append((split, render(display_split(split), "sans", self.font_size)))
    return split_max, splits

  def render(self) -> Image.Image:
    raise NotImplementedError


class BarChart(BaseBarChart):
  def __init__(self, items: Sequence[float | Item] = ()) -> None:
    super().__init__(items)
    self.width = 1280

  def _prepare_for_render(self, i: int) -> _RenderItem:
    item = self[i]
    icon = item.icon
    if icon is not None and icon.height != self.bar_width:
      icon = resize_height(icon, self.bar_width)
    return _RenderItem(
      item.value,
      name=item.name,
      icon=icon,
      palette=item.palette or self.pattern(i),
    )

  def render(self) -> Image.Image:
    items = [self._prepare_for_render(i) for i in range(len(self))]
    if self.show_values:
      value_ims = [
        render(str(item.value), "sans", self.font_size, color=item.palette.text) for item in items
      ]
      value_max_w = max(im.width for im in value_ims) + 32
    else:
      value_ims = [None] * len(items)
      value_max_w = 0
    chart_h = len(items) * self.bar_width
    header_im = render(self.title, "sans", self.font_size, align="m") if self.title else None
    header_h = header_im.height + 16 if header_im else 8
    split_max, splits = self._calc_splits()
    footer_h = max(im.height for _, im in splits) + 8
    im = Image.new("RGB", (self.width, header_h + chart_h + footer_h), self.background_color)
    if header_im:
      paste(im, header_im, (im.width / 2, 8), (0.5, 0))
    icon_w = max(item.icon.width if item.icon else 0 for item in items)
    max_w = im.width - icon_w - value_max_w
    widths = [round(item.value * max_w / split_max) for item in items]
    for i, (width, item) in enumerate(zip(widths, items, strict=True)):
      y = i * self.bar_width + header_h
      im.paste(item.palette.bg, (icon_w + width, y, im.width, y + self.bar_width))
    line_im = Image.new("RGBA", (2, chart_h), self.line_color)
    for split, split_value_im in splits:
      x = round(icon_w + split * max_w / split_max)
      im.paste(line_im, (x - 1, header_h), line_im)
      paste(im, split_value_im, (x, header_h + chart_h), (0.5, 0))
    for i, (width, value_im, item) in enumerate(zip(widths, value_ims, items, strict=True)):
      y = i * self.bar_width + header_h
      if item.icon is not None:
        paste(im, item.icon, (icon_w, y), (1, 0))
      im.paste(item.palette.fg, (icon_w, y, icon_w + width, y + self.bar_width))
      if item.name:
        value_w = value_im.width + 16 if value_im is not None else 0
        name_im = paste_text(
          im,
          (icon_w + 16, y + self.bar_width / 2),
          item.name,
          "sans",
          self.font_size,
          color=item.palette.text,
          box=im.width - icon_w - 32 - value_w,
          ellipsize="end",
          anchor=(0, 0.5),
        )
        name_width = name_im.width + 16
      else:
        name_width = 0
      if value_im is not None:
        paste(
          im,
          value_im,
          (icon_w + max(width, name_width) + 16, y + self.bar_width / 2),
          (0, 0.5),
        )
    return im


class ColumnChart(BaseBarChart):
  def __init__(self, items: Sequence[float | Item] = ()) -> None:
    super().__init__(items)
    self.height = 1280

  def _prepare_for_render(self, i: int) -> _RenderItem:
    item = self[i]
    icon = item.icon
    if icon is not None and icon.width != self.bar_width:
      icon = resize_width(icon, self.bar_width)
    return _RenderItem(
      item.value,
      name=item.name,
      icon=icon,
      palette=item.palette or self.pattern(i),
    )

  def render(self) -> Image.Image:
    items = [self._prepare_for_render(i) for i in range(len(self))]
    if self.show_values:
      value_ims = [
        render(str(item.value), "sans", self.font_size, color=item.palette.text).transpose(
          Image.Transpose.ROTATE_90,
        )
        for item in items
      ]
      value_max_h = max(im.height for im in value_ims) + 32
    else:
      value_ims = [None] * len(items)
      value_max_h = 0
    header_im = render(self.title, "sans", self.font_size, align="m") if self.title else None
    header_h = header_im.height + 16 if header_im else 8
    split_max, splits = self._calc_splits()
    split_w = max(im.width for _, im in splits) + 16
    chart_w = len(items) * self.bar_width
    im = Image.new("RGB", (split_w + chart_w, self.height), self.background_color)
    if header_im:
      paste(im, header_im, (im.width / 2, 8), (0.5, 0))
    icon_h = max(item.icon.height if item.icon else 8 for item in items)
    chart_h = im.height - header_h - icon_h
    max_h = chart_h - value_max_h
    heights = [round(item.value * max_h // split_max) for item in items]
    for i, (height, item) in enumerate(zip(heights, items, strict=True)):
      x = i * self.bar_width + split_w
      im.paste(item.palette.bg, (x, header_h, x + self.bar_width, header_h + chart_h - height))
    line_im = Image.new("RGBA", (chart_w, 2), self.line_color)
    for split, split_value_im in splits:
      y = round(header_h + chart_h - split * max_h // split_max)
      im.paste(line_im, (split_w, y - 1), line_im)
      paste(im, split_value_im, (split_w - 8, y), (1, 0.5))
    for i, (height, value_im, item) in enumerate(zip(heights, value_ims, items, strict=True)):
      x = split_w + i * self.bar_width
      if item.icon is not None:
        paste(im, item.icon, (x, header_h + chart_h))
      im.paste(
        item.palette.fg,
        (x, header_h + chart_h - height, x + self.bar_width, header_h + chart_h),
      )
      if item.name:
        value_h = value_im.height + 16 if value_im is not None else 0
        name_im = render(
          item.name,
          "sans",
          self.font_size,
          color=item.palette.text,
          box=chart_h - 32 - value_h,
          ellipsize="end",
        ).transpose(Image.Transpose.ROTATE_90)
        paste(im, name_im, (x + self.bar_width / 2, header_h + chart_h - 16), (0.5, 1))
        name_h = name_im.height + 16
      else:
        name_h = 0
      if value_im is not None:
        paste(
          im,
          value_im,
          (x + self.bar_width / 2, header_h + chart_h - max(height, name_h) - 16),
          (0.5, 1),
        )
    return im
