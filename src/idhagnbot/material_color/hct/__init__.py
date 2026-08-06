"""
A color system built using CAM16 hue and chroma, and L* from L*a*b*.

Using L* creates a link between the color system, contrast, and thus accessibility. Contrast ratio
depends on relative luminance, or Y in the XYZ color space. L*, or perceptual luminance can be
calculated from Y.

Unlike Y, L* is linear to human perception, allowing trivial creation of accurate color tones.

Unlike contrast ratio, measuring contrast in L* is linear, and simple to calculate. A difference of
40 in HCT tone guarantees a contrast ratio >= 3.0, and a difference of 50 guarantees a contrast
ratio >= 4.5.
"""

from idhagnbot.material_color.color_utils import argb_from_lstar, lstar_from_argb
from idhagnbot.material_color.hct.cam16 import Cam16
from idhagnbot.material_color.hct.viewing_conditions import ViewingConditions
from idhagnbot.material_color.math_utils import clamp, sanitize_degrees

_CHROMA_SEARCH_ENDPOINT = 0.4
"""
When the delta between the floor & ceiling of a binary search for maximum chroma at a hue and tone
is less than this, the binary search terminates.
"""

_DE_MAX = 1.0
"""The maximum color distance, in CAM16-UCS, between a requested color and the color returned."""

_DL_MAX = 0.2
"""The maximum difference between the requested L* and the L* returned."""

_LIGHTNESS_SEARCH_ENDPOINT = 0.01
"""
When the delta between the floor & ceiling of a binary search for J, lightness in CAM16, is less
than this, the binary search terminates.
"""


def _find_cam_by_j(hue: float, chroma: float, tone: float) -> Cam16 | None:
  """
  :param hue: CAM16 hue
  :param chroma: CAM16 chroma
  :param tone: L*a*b* lightness
  :return: CAM16 instance within error tolerance of the provided dimensions, or null.
  """
  low = 0.0
  high = 100.0
  best_dl = 1000.0
  best_de = 1000.0
  best_cam = None
  while abs(low - high) > _LIGHTNESS_SEARCH_ENDPOINT:
    mid = low + (high - low) / 2
    cam_before_clip = Cam16.from_jch(mid, chroma, hue)
    clipped = int(cam_before_clip)
    clipped_lstar = lstar_from_argb(clipped)
    dl = abs(tone - clipped_lstar)
    if dl < _DL_MAX:
      cam_clipped = Cam16.from_argb(clipped)
      de = cam_clipped.distance(Cam16.from_jch(cam_clipped.j, cam_clipped.chroma, hue))
      if de <= _DE_MAX and de <= best_de:
        best_dl = dl
        best_de = de
        best_cam = cam_clipped
    if best_dl == 0 and best_de == 0:
      break
    if clipped_lstar < tone:
      low = mid
    else:
      high = mid
  return best_cam


def _to_argb(
  hue: float,
  chroma: float,
  tone: float,
  viewing_conditions: ViewingConditions = ViewingConditions.DEFAULT,
) -> int:
  """
  :param hue: a number, in degrees, representing ex. red, orange, yellow, etc.
              Ranges from 0 <= hue < 360.
  :param chroma: Informally, colorfulness. Ranges from 0 to roughly 150. Like all perceptually
                 accurate color systems, chroma has a different maximum for any given hue and tone,
                 so the color returned may be lower than the requested chroma.
  :param tone: Lightness. Ranges from 0 to 100.
  :param viewing_conditions: Information about the environment where the color was observed.
  :return: ARGB representation of a color in default viewing conditions
  """
  hue = sanitize_degrees(hue)
  tone = clamp(0.0, 100.0, tone)

  if chroma < 1.0 or round(tone) <= 0.0 or round(tone) >= 100.0:
    return argb_from_lstar(tone)

  high = chroma
  mid = chroma
  low = 0.0
  is_first_loop = True
  answer = None
  while abs(low - high) >= _CHROMA_SEARCH_ENDPOINT:
    possible_answer = _find_cam_by_j(hue, mid, tone)
    if is_first_loop:
      if possible_answer is not None:
        return possible_answer.to_argb(viewing_conditions)
      is_first_loop = False
      mid = low + (high - low) / 2.0
      continue
    if possible_answer is None:
      high = mid
    else:
      answer = possible_answer
      low = mid
    mid = low + (high - low) / 2.0
  if answer is None:
    return argb_from_lstar(tone)
  return answer.to_argb(viewing_conditions)


class Hct:
  """
  HCT, hue, chroma, and tone. A color system that provides a perceptually accurate color
  measurement system that can also accurately render what colors will appear as in different
  lighting environments.
  """

  def __init__(self, hue: float, chroma: float, tone: float) -> None:
    self._set_argb(_to_argb(hue, chroma, tone))

  @staticmethod
  def from_argb(argb: int) -> "Hct":
    """
    :param argb: ARGB representation of a color.
    :return: HCT representation of a color in default viewing conditions
    """
    cam = Cam16.from_argb(argb)
    tone = lstar_from_argb(argb)
    return Hct(cam.hue, cam.chroma, tone)

  def __int__(self) -> int:
    return _to_argb(self._hue, self._chroma, self._tone)

  @property
  def hue(self) -> float:
    """
    A number, in degrees, representing ex. red, orange, yellow, etc. Ranges from 0 <= hue < 360.
    """
    return self._hue

  @hue.setter
  def hue(self, value: float) -> None:
    """
    :param value: 0 <= hue < 360; invalid values are corrected.
    Chroma may decrease because chroma has a different maximum for any given hue and tone.
    """
    self._set_argb(_to_argb(sanitize_degrees(value), self._chroma, self._tone))

  @property
  def chroma(self) -> float:
    return self._chroma

  @chroma.setter
  def chroma(self, value: float) -> None:
    """
    :param value: 0 <= chroma < ?
    Chroma may decrease because chroma has a different maximum for any given hue and tone.
    """
    self._set_argb(_to_argb(self._hue, value, self._tone))

  @property
  def tone(self) -> float:
    """Lightness. Ranges from 0 to 100."""
    return self._tone

  @tone.setter
  def tone(self, value: float) -> None:
    """
    :param value: 0 <= tone <= 100; invalid valids are corrected.
    Chroma may decrease because chroma has a different maximum for any given hue and tone.
    """
    self._set_argb(_to_argb(self._hue, self._chroma, value))

  def _set_argb(self, argb: int) -> None:
    cam = Cam16.from_argb(argb)
    self._hue = cam.hue
    self._chroma = cam.chroma
    self._tone = lstar_from_argb(argb)
