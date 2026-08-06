"""
Quantizes an image into a map, with keys of ARGB colors, and values of the number of times that
color appears in the image.
"""

from collections import OrderedDict
from collections.abc import Iterable

from idhagnbot.material_color.color_utils import alpha_from_argb


def quantize(pixels: Iterable[int]) -> OrderedDict[int, int]:
  """
  :param pixels: Colors in ARGB format.
  :return: A Map with keys of ARGB colors, and values of the number of times the color appears in
           the image.
  """
  count_by_color = OrderedDict[int, int]()
  for pixel in pixels:
    alpha = alpha_from_argb(pixel)
    if alpha < 255:
      continue
    count_by_color[pixel] = count_by_color.get(pixel, 0) + 1
  return count_by_color
