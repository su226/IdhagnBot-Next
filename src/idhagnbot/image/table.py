from collections.abc import Callable, Sequence
from dataclasses import KW_ONLY, dataclass
from dataclasses import replace as dc_replace
from functools import cached_property
from typing import TYPE_CHECKING, Protocol, Self, TypedDict, Unpack, final

from PIL import Image
from typing_extensions import override

from idhagnbot.color import RGB, split_rgb
from idhagnbot.image import Color, Point, paste, replace

Pattern = Callable[[int, int], Color | None]
"""
单元格的背景颜色计算函数，输入横坐标和纵坐标，返回 None 代表和表格背景颜色相同，返回 int 或三元组
(int, int, int) 代表指定颜色。
"""

MPBValue = int | tuple[int] | tuple[int, int] | tuple[int, int, int] | tuple[int, int, int, int]
"""
CSS 风格的外边距（margin）、内边距（padding）或边框宽度（border-width）值。

int 或 tuple[int]：四边等宽。
tuple[int, int]：上下、左右。
tuple[int, int, int]：上、左右、下。
tuple[int, int, int, int]：上、右、下、左。
"""


@dataclass(frozen=True)
class MPB:
  """外边距（margin）、内边距（padding）或边框宽度（border-width）。"""

  top: int
  """上边距。"""

  right: int
  """右边距。"""

  bottom: int
  """下边距。"""

  left: int
  """左边距。"""

  def __post_init__(self) -> None:
    """校验值不能为负。"""
    if self.top < 0 or self.right < 0 or self.bottom < 0 or self.left < 0:
      # 负的 margin 在 CSS 中有意义，但在图像渲染中无意义。
      # 负的 padding 和 border-width 没有意义。
      raise ValueError("值不能为负。")

  @classmethod
  def parse(cls, value: MPBValue) -> Self:
    """
    解析 CSS 风格的外边距（Margin）或内边距（Padding）值。

    :param value: CSS 风格的边距值，int 或长度为 1 - 4 的 int 元组。
    :return: 边距值
    """
    if isinstance(value, int):
      return cls(value, value, value, value)
    if len(value) == 1:
      value = value[0]
      return cls(value, value, value, value)
    if len(value) == 2:
      y, x = value
      return cls(y, x, y, x)
    if len(value) == 3:
      top, x, bottom = value
      return cls(top, x, bottom, x)
    return cls(*value)


def pattern_full(color: Color = (240, 240, 240)) -> Pattern:
  """
  底色表格。

  :param color: 指定背景颜色。
  """
  return lambda x, y: color


def pattern_stripe(color: Color = (240, 240, 240), invert: bool = False) -> Pattern:
  """
  横向斑马纹表格。奇数行使用表格背景颜色，偶数行使用指定颜色。

  :param color: 指定背景颜色。
  :param invert: 反转模式，奇数行使用指定颜色，偶数行使用表格背景色。
  """
  return lambda x, y: color if (y & 1) ^ invert else None


def pattern_vertical_stripe(color: Color = (240, 240, 240), invert: bool = False) -> Pattern:
  """
  纵向斑马纹表格。奇数列使用表格背景颜色，偶数列使用指定颜色。

  :param color: 指定背景颜色。
  :param invert: 反转模式，奇数列使用指定颜色，偶数列使用表格背景色。
  """
  return lambda x, y: color if (x & 1) ^ invert else None


def pattern_checkerboard(color: Color = (240, 240, 240), invert: bool = False) -> Pattern:
  """
  棋盘格表格。(0, 0) 使用表格背景颜色，(0, 1)、(1, 0) 使用指定颜色，以此类推。

  :param color: 指定背景颜色。
  :param invert: 反转模式
  """
  return lambda x, y: color if ((x + y) & 1) ^ invert else None


@final
@dataclass(frozen=True)
class Cell:
  """单元格"""

  content: Image.Image | None
  """单元格内容，None 表示内容为空。"""

  _: KW_ONLY

  background: Color | None = None
  """单元格背景，None 表示由表格 pattern 和 背景颜色决定。"""

  padding: MPB | MPBValue | None = None
  """单元格内边距，None 表示和全局内边距相同。"""

  align: tuple[float, float] | None = None
  """
  单元格对齐方式，None 表示和全局对齐方式相同，先 x 后 y。
  (0, 0) 表示左上角，(0.5, 0.5) 表示居中，以此类推。
  """

  @property
  def parsed_padding(self) -> MPB | None:
    """
    解析后的内边距，None 表示和全局内边距相同。

    :returns: 解析后的内边距。
    """
    if self.padding is None:
      return None
    return self.padding if isinstance(self.padding, MPB) else MPB.parse(self.padding)


if TYPE_CHECKING:

  class _CellAttrs(TypedDict):
    """单元格参数，仅用于类型检查。"""

    background: Color | None
    """单元格背景，None 表示由表格 pattern 和 背景颜色决定。"""

    padding: MPB | MPBValue | None
    """单元格内边距，None 表示和全局内边距相同。"""

    align: tuple[float, float] | None
    """
    单元格对齐方式，None 表示和全局对齐方式相同，先 x 后 y。
    (0, 0) 表示左上角，(0.5, 0.5) 表示居中，以此类推。
    """


@final
@dataclass(frozen=True)
class _RenderCell:
  """渲染时的临时单元格，其参数已确定为指定值或全局默认。"""

  content: Image.Image | None
  """单元格内容，None 表示内容为空。"""

  _: KW_ONLY

  background: Color | None
  """单元格背景，None 表示由表格背景颜色决定。"""

  padding: MPB
  """单元格内边距。"""

  align: tuple[float, float]
  """单元格对齐方式，先 x 后 y。(0, 0) 表示左上角，(0.5, 0.5) 表示居中，以此类推。"""

  @property
  def inner_width(self) -> int:
    """
    内部宽度。

    :returns: 内部宽度。
    """
    content_width = 0 if self.content is None else self.content.width
    return self.padding.left + content_width + self.padding.right

  @property
  def inner_height(self) -> int:
    """
    内部高度。

    :returns: 内部高度。
    """
    content_height = 0 if self.content is None else self.content.height
    return self.padding.top + content_height + self.padding.bottom


class Border(Protocol):
  """表格边框。"""

  def get_color(self) -> Color:
    """
    获取边框颜色。

    :returns:边框颜色。
    """

  def get_horizontal(self, rows: int) -> Sequence[int]:
    """
    获取横向边框粗细。

    :param rows: 表格行数。
    :returns: 每一条边框的粗细，0 表示没有边框，元素数量必须为表格行数 + 1。
    """

  def get_vertical(self, columns: int) -> Sequence[int]:
    """
    获取纵向边框粗细。

    :param columns: 表格列数。
    :returns: 每一条边框的粗细，0 表示没有边框，元素数量必须为表格列数 + 1。
    """


@final
@dataclass(frozen=True)
class StandardBorder(Border):
  """标准表格边框，支持全边框、外边框、斑马纹、单线表、三线表。"""

  color: Color
  """边框颜色。"""

  width_edge: MPB | MPBValue
  """外边框粗细。"""

  width_inner_horizontal: int
  """横向内边框粗细。"""

  width_inner_vertical: int
  """纵向内边框粗细。"""

  width_separator_horizontal: int = 0
  """横向表头分割线粗细。"""

  width_separator_vertical: int = 0
  """纵向表头分割线粗细。"""

  header_len_horizontal: int = 0
  """前几行视为表头。"""

  header_len_vertical: int = 0
  """前几列视为表头。"""

  @cached_property
  def __parsed_width_edge(self) -> MPB:
    """
    解析后的外边框粗细。

    :returns: 解析后的外边框粗细。
    """
    return self.width_edge if isinstance(self.width_edge, MPB) else MPB.parse(self.width_edge)

  @override
  def get_color(self) -> Color:
    """
    获取边框颜色。

    :returns:边框颜色。
    """
    return self.color

  @override
  def get_horizontal(self, rows: int) -> list[int]:
    """
    获取横向边框粗细。

    :param rows: 表格行数。
    :returns: 每一条边框的粗细，0 表示没有边框，元素数量必须为表格行数 + 1。
    """
    borders = (
      [self.__parsed_width_edge.top]
      + [self.width_inner_horizontal] * (rows - 1)
      + [self.__parsed_width_edge.bottom]
    )
    if 0 < self.header_len_horizontal < rows:
      borders[self.header_len_horizontal] = self.width_separator_horizontal
    return borders

  @override
  def get_vertical(self, columns: int) -> list[int]:
    """
    获取纵向边框粗细。

    :param columns: 表格列数。
    :returns: 每一条边框的粗细，0 表示没有边框，元素数量必须为表格列数 + 1。
    """
    borders = (
      [self.__parsed_width_edge.left]
      + [self.width_inner_vertical] * (columns - 1)
      + [self.__parsed_width_edge.right]
    )
    if 0 < self.header_len_vertical < columns:
      borders[self.header_len_vertical] = self.width_separator_vertical
    return borders


@final
class Table:
  """表格图像构建器。"""

  __cells: list[list[Cell | Image.Image | None]]
  """单元格矩阵，先 y 后 x。每一行的元素可以不满。"""

  __rows: int
  """行数。"""

  __columns: int
  """列数。"""

  __margin: MPB
  """外边距。"""

  __padding: MPB
  """内边距。"""

  __background_color: RGB
  """背景颜色，会填充外边距范围。"""

  align: Point
  """默认对齐方式，先 x 后 y。(0, 0) 表示左上角，(0.5, 0.5) 表示居中，以此类推。"""

  pattern: Pattern | None
  """单元格背景模式。"""

  border: Border | None
  """表格边框。"""

  def __init__(self, cells: Sequence[Sequence[Cell | Image.Image | None]]) -> None:
    """
    创建一个表格构建器。

    :param cells: 初始单元格矩阵，先 y 后 x，每一行的元素可以不满。
    """
    self.__cells = [list(row) for row in cells]
    self.__rows = len(cells)
    self.__columns = max(len(row) for row in cells)
    self.__margin = MPB(0, 0, 0, 0)
    self.__padding = MPB(0, 0, 0, 0)
    self.__background_color = (255, 255, 255)
    self.align = (0.5, 0.5)
    self.pattern = None
    self.border = StandardBorder((224, 224, 224), 2, 2, 2)

  @property
  def rows(self) -> int:
    """
    行数。

    :returns: 行数。
    """
    return self.__rows

  @property
  def columns(self) -> int:
    """
    列数。

    :returns: 列数。
    """
    return self.__columns

  @property
  def margin(self) -> MPB:
    """
    外边距。

    :returns: 外边距。
    """
    return self.__margin

  @margin.setter
  def margin(self, value: MPB | MPBValue) -> None:
    """
    外边距。

    :param value: 外边距。
    """
    self.__margin = value if isinstance(value, MPB) else MPB.parse(value)

  @property
  def padding(self) -> MPB:
    """
    内边距。

    :returns: 内边距。
    """
    return self.__padding

  @padding.setter
  def padding(self, value: MPB | MPBValue) -> None:
    """
    内边距。

    :param value: 内边距。
    """
    self.__padding = value if isinstance(value, MPB) else MPB.parse(value)

  @property
  def background_color(self) -> RGB:
    """
    背景颜色，会填充外边距范围。

    :returns: 背景颜色。
    """
    return self.__background_color

  @background_color.setter
  def background_color(self, value: Color) -> None:
    """
    背景颜色，会填充外边距范围。

    :param value: 背景颜色。
    """
    self.__background_color = split_rgb(value) if isinstance(value, int) else value

  def append_row(self, row: list[Cell | Image.Image | None]) -> None:
    """
    在尾部增加一行，列数可以不匹配。

    :param row: 增加的行。
    """
    self.__cells.append(row)
    self.__rows += 1
    self.__columns = max(self.__columns, len(row))

  def append_column(self, column: list[Cell | Image.Image | None]) -> None:
    """
    在尾部增加一列，行数可以不匹配。

    :param row: 增加的列。
    """
    while len(self.__cells) < len(column):
      self.__cells.append([])
      self.__rows += 1
    for row, cell in zip(self.__cells, column, strict=False):
      while len(row) < self.__columns:
        row.append(None)
      row.append(cell)
    self.__columns += 1

  def set_row_attrs(self, y: int, **kw: Unpack["_CellAttrs"]) -> None:
    """
    设置行参数。

    :param y: 第几行。
    :param kw: 替换的参数，不传入表示保持原样。
    """
    for x in range(self.__columns):
      self[x, y] = dc_replace(self[x, y], **kw)

  def set_column_attrs(self, x: int, **kw: Unpack["_CellAttrs"]) -> None:
    """
    设置列参数。

    :param y: 第几列。
    :param kw: 替换的参数，不传入表示保持原样。
    """
    for y in range(self.__rows):
      self[x, y] = dc_replace(self[x, y], **kw)

  def __getitem__(self, xy: tuple[int, int]) -> Cell:
    """
    获取单元格。

    :param xy: 二元组坐标，先 x 后 y。
    :returns: 单元格。
    """
    x, y = xy
    if not (0 <= x < self.__columns) or not (0 <= y < self.__rows):
      raise IndexError(x, y)
    row = self.__cells[y]
    if x > len(row):
      return Cell(None)
    cell = row[x]
    return cell if isinstance(cell, Cell) else Cell(cell)

  def __setitem__(self, xy: tuple[int, int], cell: Cell | Image.Image | None) -> None:
    """
    设置单元格。

    :param xy: 二元组坐标，先 x 后 y。
    :param cell: 单元格。
    """
    x, y = xy
    if not (0 <= x < self.__columns) or not (0 <= y < self.__rows):
      raise IndexError(x, y)
    row = self.__cells[y]
    while x > len(row):
      row.append(None)
    row[x] = cell

  def __prepare_cell_for_render(self, x: int, y: int) -> _RenderCell:
    """
    将单元格里的可选参数填入全局默认值，用于渲染。

    :param x: 横坐标。
    :param y: 纵坐标。
    :returns: 渲染时的临时单元格。
    """
    cell = self[x, y]
    padding = cell.parsed_padding or self.__padding
    background = cell.background
    if background is None and self.pattern is not None:
      background = self.pattern(x, y)
    align = cell.align or self.align
    return _RenderCell(cell.content, background=background, padding=padding, align=align)

  def render(self) -> Image.Image:
    """
    渲染表格到图像。

    :returns: 表格图像，RGB 模式。
    """
    cells = [
      [self.__prepare_cell_for_render(x, y) for x in range(self.__columns)]
      for y in range(self.__rows)
    ]
    column_count = max(len(row) for row in cells)
    column_widths = [
      max(cells[y][x].inner_width for y in range(len(cells))) for x in range(column_count)
    ]
    row_count = len(cells)
    row_heights = [max(cell.inner_height for cell in row) for row in cells]
    if self.border:
      borders_v = self.border.get_vertical(column_count)
      if len(borders_v) != column_count + 1:
        raise ValueError(f"边框列数不匹配，需要 {column_count + 1}，得到 {len(borders_v)}。")
      if any(x < 0 for x in borders_v):
        raise ValueError("边框粗细不能为负。")
      borders_h = self.border.get_horizontal(row_count)
      if len(borders_h) != row_count + 1:
        raise ValueError(f"边框行数不匹配，需要 {row_count + 1}，得到 {len(borders_h)}。")
      if any(x < 0 for x in borders_h):
        raise ValueError("边框粗细不能为负。")
      borders_color = self.border.get_color()
    else:
      borders_v = [0] * (column_count + 1)
      borders_h = [0] * (row_count + 1)
      borders_color = (0, 0, 0)
    borders_width = sum(borders_v)
    borders_height = sum(borders_h)
    table_width = sum(column_widths) + borders_width
    table_height = sum(row_heights) + borders_height
    image_width = table_width + self.__margin.left + self.__margin.right
    image_height = table_height + self.__margin.top + self.__margin.bottom
    image = Image.new("RGB", (image_width, image_height), self.__background_color)

    x = self.__margin.left
    for border, column_width in zip(borders_v, column_widths, strict=False):
      if border > 0:
        replace(image, (borders_color, (border, table_height)), (x, self.__margin.top))
        x += border
      x += column_width
    if (border := borders_v[-1]) > 0:
      replace(image, (borders_color, (border, table_height)), (x, self.__margin.top))

    y = self.__margin.top
    for border, row_height in zip(borders_h, row_heights, strict=False):
      if border > 0:
        replace(image, (borders_color, (table_width, border)), (self.__margin.left, y))
        y += border
      y += row_height
    if (border := borders_h[-1]) > 0:
      replace(image, (borders_color, (table_width, border)), (self.__margin.left, y))

    y = self.__margin.top
    for table_y, (row, border_h) in enumerate(zip(cells, borders_h, strict=False)):
      if border_h is not None:
        y += border_h
      row_height = row_heights[table_y]
      x = self.__margin.left
      for table_x, (cell, border_v) in enumerate(zip(row, borders_v, strict=False)):
        if border_v is not None:
          x += border_v
        column_width = column_widths[table_x]
        if cell.background is not None:
          replace(image, (cell.background, (column_width, row_height)), (x, y))
        if cell.content is not None:
          paste_x = x + round(
            cell.padding.left
            + (column_width - cell.padding.left - cell.padding.right - cell.content.width)
            * cell.align[0],
          )
          paste_y = y + round(
            cell.padding.top
            + (row_height - cell.padding.top - cell.padding.bottom - cell.content.height)
            * cell.align[1],
          )
          paste(image, cell.content, (paste_x, paste_y))
        x += column_width
      y += row_height

    return image
