"""
An image quantizer that divides the image's pixels into clusters by recursively cutting
an RGB cube, based on the weight of pixels in each area of the cube.

The algorithm was described by Xiaolin Wu in Graphic Gems II, published in 1991.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from idhagnbot.material_color.color_utils import (
    blue_from_argb,
    green_from_argb,
    red_from_argb,
)
from idhagnbot.material_color.quantize import quantizer_map

_INDEX_BITS = 5
_SIDE_LENGTH = 33  # ((1 << INDEX_INDEX_BITS) + 1)
_TOTAL_SIZE = 35937  # SIDE_LENGTH * SIDE_LENGTH * SIDE_LENGTH


class _Directions(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


@dataclass
class _Box:
    """
    Keeps track of the state of each box created as the Wu quantization algorithm
    progresses through dividing the image's pixels as plotted in RGB.
    """

    r0: int = 0
    r1: int = 0
    g0: int = 0
    g1: int = 0
    b0: int = 0
    b1: int = 0
    vol: int = 0


@dataclass
class _CreateBoxesResult:
    """Represents final result of Wu algorithm."""

    requested_count: int
    """how many colors the caller asked to be returned from quantization."""
    result_count: int
    """
    the actual number of colors achieved from quantization. May be lower than the
    requested count.
    """


@dataclass
class _MaximizeResult:
    """
    Represents the result of calculating where to cut an existing box in such a way to
    maximize variance between the two new boxes created by a cut.
    """

    cut_location: int
    maximum: float


def _get_index(r: int, g: int, b: int) -> int:
    return (
        (r << (_INDEX_BITS * 2))
        + (r << (_INDEX_BITS + 1))
        + r
        + (g << _INDEX_BITS)
        + g
        + b
    )


def _volume(cube: _Box, moment: list[int]) -> int:
    return (
        moment[_get_index(cube.r1, cube.g1, cube.b1)]
        - moment[_get_index(cube.r1, cube.g1, cube.b0)]
        - moment[_get_index(cube.r1, cube.g0, cube.b1)]
        + moment[_get_index(cube.r1, cube.g0, cube.b0)]
        - moment[_get_index(cube.r0, cube.g1, cube.b1)]
        + moment[_get_index(cube.r0, cube.g1, cube.b0)]
        + moment[_get_index(cube.r0, cube.g0, cube.b1)]
        - moment[_get_index(cube.r0, cube.g0, cube.b0)]
    )


def _bottom(cube: _Box, direction: _Directions, moment: list[int]) -> int:
    if direction == _Directions.RED:
        return (
            -moment[_get_index(cube.r0, cube.g1, cube.b1)]
            + moment[_get_index(cube.r0, cube.g1, cube.b0)]
            + moment[_get_index(cube.r0, cube.g0, cube.b1)]
            - moment[_get_index(cube.r0, cube.g0, cube.b0)]
        )
    if direction == _Directions.GREEN:
        return (
            -moment[_get_index(cube.r1, cube.g0, cube.b1)]
            + moment[_get_index(cube.r1, cube.g0, cube.b0)]
            + moment[_get_index(cube.r0, cube.g0, cube.b1)]
            - moment[_get_index(cube.r0, cube.g0, cube.b0)]
        )
    return (
        -moment[_get_index(cube.r1, cube.g1, cube.b0)]
        + moment[_get_index(cube.r1, cube.g0, cube.b0)]
        + moment[_get_index(cube.r0, cube.g1, cube.b0)]
        - moment[_get_index(cube.r0, cube.g0, cube.b0)]
    )


def _top(cube: _Box, direction: _Directions, position: int, moment: list[int]) -> int:
    if direction == _Directions.RED:
        return (
            moment[_get_index(position, cube.g1, cube.b1)]
            - moment[_get_index(position, cube.g1, cube.b0)]
            - moment[_get_index(position, cube.g0, cube.b1)]
            + moment[_get_index(position, cube.g0, cube.b0)]
        )
    if direction == _Directions.GREEN:
        return (
            moment[_get_index(cube.r1, position, cube.b1)]
            - moment[_get_index(cube.r1, position, cube.b0)]
            - moment[_get_index(cube.r0, position, cube.b1)]
            + moment[_get_index(cube.r0, position, cube.b0)]
        )
    return (
        moment[_get_index(cube.r1, cube.g1, position)]
        - moment[_get_index(cube.r1, cube.g0, position)]
        - moment[_get_index(cube.r0, cube.g1, position)]
        + moment[_get_index(cube.r0, cube.g0, position)]
    )


class _QuantizerWu:
    def __init__(self) -> None:
        self.weights: list[int] = []
        self.momentsR: list[int] = []
        self.momentsG: list[int] = []
        self.momentsB: list[int] = []
        self.moments: list[int] = []
        self.cubes: list[_Box] = []

    def construct_histogram(self, pixels: Iterable[int]) -> None:
        self.weights = [0] * _TOTAL_SIZE
        self.momentsR = [0] * _TOTAL_SIZE
        self.momentsG = [0] * _TOTAL_SIZE
        self.momentsB = [0] * _TOTAL_SIZE
        self.moments = [0] * _TOTAL_SIZE
        count_by_color = quantizer_map.quantize(pixels)
        for pixel, count in count_by_color.items():
            red = red_from_argb(pixel)
            green = green_from_argb(pixel)
            blue = blue_from_argb(pixel)
            bits_to_remove = 8 - _INDEX_BITS
            ir = (red >> bits_to_remove) + 1
            ig = (green >> bits_to_remove) + 1
            ib = (blue >> bits_to_remove) + 1
            index = _get_index(ir, ig, ib)
            self.weights[index] = (
                self.weights[index] if len(self.weights) > index else 0
            ) + count
            self.momentsR[index] += count * red
            self.momentsG[index] += count * green
            self.momentsB[index] += count * blue
            self.moments[index] += count * (red * red + green * green + blue * blue)

    def compute_moments(self) -> None:
        for r in range(1, _SIDE_LENGTH):
            area = [0] * _SIDE_LENGTH
            area_r = [0] * _SIDE_LENGTH
            area_g = [0] * _SIDE_LENGTH
            area_b = [0] * _SIDE_LENGTH
            area2 = [0] * _SIDE_LENGTH
            for g in range(1, _SIDE_LENGTH):
                line = 0
                line_r = 0
                line_g = 0
                line_b = 0
                line2 = 0
                for b in range(1, _SIDE_LENGTH):
                    index = _get_index(r, g, b)
                    line += self.weights[index]
                    line_r += self.momentsR[index]
                    line_g += self.momentsG[index]
                    line_b += self.momentsB[index]
                    line2 += self.moments[index]
                    area[b] += line
                    area_r[b] += line_r
                    area_g[b] += line_g
                    area_b[b] += line_b
                    area2[b] += line2
                    previous_index = _get_index(r - 1, g, b)
                    self.weights[index] = self.weights[previous_index] + area[b]
                    self.momentsR[index] = self.momentsR[previous_index] + area_r[b]
                    self.momentsG[index] = self.momentsG[previous_index] + area_g[b]
                    self.momentsB[index] = self.momentsB[previous_index] + area_b[b]
                    self.moments[index] = self.moments[previous_index] + area2[b]

    def create_boxes(self, max_colors: int) -> _CreateBoxesResult:
        self.cubes = [_Box() for _ in range(max_colors)]
        volume_variance = [0.0] * max_colors
        self.cubes[0].r0 = 0
        self.cubes[0].g0 = 0
        self.cubes[0].b0 = 0
        self.cubes[0].r1 = _SIDE_LENGTH - 1
        self.cubes[0].g1 = _SIDE_LENGTH - 1
        self.cubes[0].b1 = _SIDE_LENGTH - 1
        generated_color_count = max_colors
        next_i = 0
        i = 1
        while i < max_colors:
            if self.cut(self.cubes[next_i], self.cubes[i]):
                volume_variance[next_i] = (
                    self.variance(self.cubes[next_i])
                    if self.cubes[next_i].vol > 1
                    else 0.0
                )
                volume_variance[i] = (
                    self.variance(self.cubes[i]) if self.cubes[i].vol > 1 else 0.0
                )
            else:
                volume_variance[next_i] = 0.0
                i -= 1
            next_i = 0
            temp = volume_variance[0]
            for j in range(1, i):
                if volume_variance[j] > temp:
                    temp = volume_variance[j]
                    next_i = j
            if temp <= 0.0:
                generated_color_count = i + 1
                break
            i += 1
        return _CreateBoxesResult(max_colors, generated_color_count)

    def create_result(self, color_count: int) -> list[int]:
        colors: list[int] = []
        for i in range(color_count):
            cube = self.cubes[i]
            weight = _volume(cube, self.weights)
            if weight > 0:
                r = round(_volume(cube, self.momentsR) / weight)
                g = round(_volume(cube, self.momentsG) / weight)
                b = round(_volume(cube, self.momentsB) / weight)
                color = (
                    (255 << 24) | ((r & 0x0FF) << 16) | ((g & 0x0FF) << 8) | (b & 0x0FF)
                )
                colors.append(color)
        return colors

    def variance(self, cube: _Box) -> float:
        dr = _volume(cube, self.momentsR)
        dg = _volume(cube, self.momentsG)
        db = _volume(cube, self.momentsB)
        xx = (
            self.moments[_get_index(cube.r1, cube.g1, cube.b1)]
            - self.moments[_get_index(cube.r1, cube.g1, cube.b0)]
            - self.moments[_get_index(cube.r1, cube.g0, cube.b1)]
            + self.moments[_get_index(cube.r1, cube.g0, cube.b0)]
            - self.moments[_get_index(cube.r0, cube.g1, cube.b1)]
            + self.moments[_get_index(cube.r0, cube.g1, cube.b0)]
            + self.moments[_get_index(cube.r0, cube.g0, cube.b1)]
            - self.moments[_get_index(cube.r0, cube.g0, cube.b0)]
        )
        hypotenuse = dr * dr + dg * dg + db * db
        return xx - hypotenuse / _volume(cube, self.weights)

    def cut(self, one: _Box, two: _Box) -> bool:
        whole_r = _volume(one, self.momentsR)
        whole_g = _volume(one, self.momentsG)
        whole_b = _volume(one, self.momentsB)
        whole_w = _volume(one, self.weights)
        max_r_result = self.maximize(
            one,
            _Directions.RED,
            one.r0 + 1,
            one.r1,
            whole_r,
            whole_g,
            whole_b,
            whole_w,
        )
        max_g_result = self.maximize(
            one,
            _Directions.GREEN,
            one.g0 + 1,
            one.g1,
            whole_r,
            whole_g,
            whole_b,
            whole_w,
        )
        max_b_result = self.maximize(
            one,
            _Directions.BLUE,
            one.b0 + 1,
            one.b1,
            whole_r,
            whole_g,
            whole_b,
            whole_w,
        )
        max_r = max_r_result.maximum
        max_g = max_g_result.maximum
        max_b = max_b_result.maximum
        if max_r >= max_g and max_r >= max_b:
            if max_r_result.cut_location < 0:
                return False
            direction = _Directions.RED
        elif max_g >= max_r and max_g >= max_b:
            direction = _Directions.GREEN
        else:
            direction = _Directions.BLUE
        two.r1 = one.r1
        two.g1 = one.g1
        two.b1 = one.b1

        if direction == _Directions.RED:
            one.r1 = max_r_result.cut_location
            two.r0 = one.r1
            two.g0 = one.g0
            two.b0 = one.b0
        elif direction == _Directions.GREEN:
            one.g1 = max_g_result.cut_location
            two.r0 = one.r0
            two.g0 = one.g1
            two.b0 = one.b0
        else:
            one.b1 = max_b_result.cut_location
            two.r0 = one.r0
            two.g0 = one.g0
            two.b0 = one.b1

        one.vol = (one.r1 - one.r0) * (one.g1 - one.g0) * (one.b1 - one.b0)
        two.vol = (two.r1 - two.r0) * (two.g1 - two.g0) * (two.b1 - two.b0)
        return True

    def maximize(
        self,
        cube: _Box,
        direction: _Directions,
        first: int,
        last: int,
        whole_r: int,
        whole_g: int,
        whole_b: int,
        whole_w: int,
    ) -> _MaximizeResult:
        bottom_r = _bottom(cube, direction, self.momentsR)
        bottom_g = _bottom(cube, direction, self.momentsG)
        bottom_b = _bottom(cube, direction, self.momentsB)
        bottom_w = _bottom(cube, direction, self.weights)
        max_result = 0.0
        cut = -1
        for i in range(first, last):
            half_r = bottom_r + _top(cube, direction, i, self.momentsR)
            half_g = bottom_g + _top(cube, direction, i, self.momentsG)
            half_b = bottom_b + _top(cube, direction, i, self.momentsB)
            half_w = bottom_w + _top(cube, direction, i, self.weights)
            if half_w == 0:
                continue
            temp_numerator = (half_r * half_r + half_g * half_g + half_b * half_b) * 1.0
            temp_denominator = half_w * 1.0
            temp = temp_numerator / temp_denominator
            half_r = whole_r - half_r
            half_g = whole_g - half_g
            half_b = whole_b - half_b
            half_w = whole_w - half_w
            if half_w == 0:
                continue
            temp_numerator = (half_r * half_r + half_g * half_g + half_b * half_b) * 1.0
            temp_denominator = half_w * 1.0
            temp += temp_numerator / temp_denominator
            if temp > max_result:
                max_result = temp
                cut = i
        return _MaximizeResult(cut, max_result)


def quantize(pixels: Iterable[int], max_colors: int) -> list[int]:
    """
    :param pixels: Colors in ARGB format.
    :param max_colors: The number of colors to divide the image into. A lower number of
                       colors may be returned.
    :return: Colors in ARGB format.
    """
    quantizer = _QuantizerWu()
    quantizer.construct_histogram(pixels)
    quantizer.compute_moments()
    create_boxes_result = quantizer.create_boxes(max_colors)
    return quantizer.create_result(create_boxes_result.result_count)
