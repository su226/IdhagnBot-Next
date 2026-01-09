from PIL import Image

from idhagnbot.image import Color, paste, replace


def make_table(
  table: list[list[Image.Image]],
  background_color: Color = (255, 255, 255),
  border_size_h: int = 2,
  border_size_v: int = 2,
  border_color: Color = (224, 224, 224),
  margin: int = 0,
) -> Image.Image:
  column_count = max(len(row) for row in table)
  column_widths = [
    max(0 if j > len(table[i]) else table[i][j].width for i in range(len(table)))
    for j in range(column_count)
  ]
  row_count = len(table)
  row_heights = [max(cell.height for cell in row) for row in table]
  table_width = sum(column_widths) + (column_count + 1) * border_size_v
  table_height = sum(row_heights) + (row_count + 1) * border_size_h
  image_width = table_width + margin * 2
  image_height = table_height + margin * 2
  image = Image.new("RGB", (image_width, image_height), background_color)
  x = margin
  replace(image, (border_color, (border_size_v, table_height)), (x, margin))
  for column_width in column_widths:
    x += column_width + border_size_v
    replace(image, (border_color, (border_size_v, table_height)), (x, margin))
  y = margin
  replace(image, (border_color, (table_width, border_size_h)), (margin, y))
  for row_height in row_heights:
    y += row_height + border_size_h
    replace(image, (border_color, (table_width, border_size_h)), (margin, y))
  y = margin + border_size_h
  for table_y, row in enumerate(table):
    row_height = row_heights[table_y]
    x = margin + border_size_v
    for table_x, cell in enumerate(row):
      column_width = column_widths[table_x]
      paste_y = y + (row_height - cell.height) // 2
      paste_x = x + (column_width - cell.width) // 2
      paste(image, cell, (paste_x, paste_y))
      x += border_size_h + column_width
    y += border_size_v + row_height
  return image
