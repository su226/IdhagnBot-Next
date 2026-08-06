"""
Color science utilities.

Utility methods for color science constants and color space
conversions that aren't HCT or CAM16.
"""

import math

from .math_utils import Mat3x3f, Vec3f, clamp, matrix_multiply

_SRGB_TO_XYZ: Mat3x3f = (
    (0.41233895, 0.35762064, 0.18051042),
    (0.2126, 0.7152, 0.0722),
    (0.01932141, 0.11916382, 0.95034478),
)
_XYZ_TO_SRGB: Mat3x3f = (
    (3.2413774792388685, -1.5376652402851851, -0.49885366846268053),
    (-0.9691452513005321, 1.8758853451067872, 0.04156585616912061),
    (0.05562093689691305, -0.20395524564742123, 1.0571799111220335),
)
WHITE_POINT_D65: Vec3f = (95.047, 100.0, 108.883)


def argb_from_rgb(red: int, green: int, blue: int) -> int:
    """Converts a color from RGB components to ARGB format."""
    return 255 << 24 | (red & 255) << 16 | (green & 255) << 8 | blue & 255


def alpha_from_argb(argb: int) -> int:
    """Returns the alpha component of a color in ARGB format."""
    return argb >> 24 & 255


def red_from_argb(argb: int) -> int:
    """Returns the red component of a color in ARGB format."""
    return argb >> 16 & 255


def green_from_argb(argb: int) -> int:
    """Returns the green component of a color in ARGB format."""
    return argb >> 8 & 255


def blue_from_argb(argb: int) -> int:
    """Returns the blue component of a color in ARGB format."""
    return argb & 255


def argb_from_xyz(x: float, y: float, z: float) -> int:
    """Converts a color from ARGB to XYZ."""
    matrix = _XYZ_TO_SRGB
    linear_r = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z
    linear_g = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z
    linear_b = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z
    r = delinearized(linear_r)
    g = delinearized(linear_g)
    b = delinearized(linear_b)
    return argb_from_rgb(r, g, b)


def xyz_from_argb(argb: int) -> Vec3f:
    """Converts a color from XYZ to ARGB."""
    r = linearized(red_from_argb(argb))
    g = linearized(green_from_argb(argb))
    b = linearized(blue_from_argb(argb))
    return matrix_multiply((r, g, b), _SRGB_TO_XYZ)


def lab_invf(ft: float) -> float:
    e = 216.0 / 24389.0
    kappa = 24389.0 / 27.0
    ft3 = ft * ft * ft
    if ft3 > e:
        return ft3
    return (116 * ft - 16) / kappa


def argb_from_lab(l: float, a: float, b: float) -> int:
    """Converts a color represented in Lab color space into an ARGB integer."""
    white_point = WHITE_POINT_D65
    fy = (l + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0
    x_normalized = lab_invf(fx)
    y_normalized = lab_invf(fy)
    z_normalized = lab_invf(fz)
    x = x_normalized * white_point[0]
    y = y_normalized * white_point[1]
    z = z_normalized * white_point[2]
    return argb_from_xyz(x, y, z)


def lab_f(t: float) -> float:
    e = 216.0 / 24389.0
    kappa = 24389.0 / 27.0
    if t > e:
        return math.pow(t, 1.0 / 3.0)
    return (kappa * t + 16) / 116


def lab_from_argb(argb: int) -> Vec3f:
    """
    Converts a color from ARGB representation to L*a*b* representation.
    :param argb: the ARGB representation of a color
    :return: a Lab object representing the color
    """
    linear_r = linearized(red_from_argb(argb))
    linear_g = linearized(green_from_argb(argb))
    linear_b = linearized(blue_from_argb(argb))
    matrix = _SRGB_TO_XYZ
    x = matrix[0][0] * linear_r + matrix[0][1] * linear_g + matrix[0][2] * linear_b
    y = matrix[1][0] * linear_r + matrix[1][1] * linear_g + matrix[1][2] * linear_b
    z = matrix[2][0] * linear_r + matrix[2][1] * linear_g + matrix[2][2] * linear_b
    white_point = WHITE_POINT_D65
    x_normalized = x / white_point[0]
    y_normalized = y / white_point[1]
    z_normalized = z / white_point[2]
    fx = lab_f(x_normalized)
    fy = lab_f(y_normalized)
    fz = lab_f(z_normalized)
    l = 116.0 * fy - 16
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return (l, a, b)


def argb_from_lstar(lstar: float) -> int:
    """
    Converts an L* value to an ARGB representation.
    :param lstar: L* in L*a*b*
    :return: ARGB representation of grayscale color with lightness matching L*
    """
    y = y_from_lstar(lstar)
    component = delinearized(y)
    return argb_from_rgb(component, component, component)


def lstar_from_argb(argb: int) -> float:
    """
    Computes the L* value of a color in ARGB representation.
    :param argb: ARGB representation of a color
    :return: L*, from L*a*b*, coordinate of the color
    """
    y = xyz_from_argb(argb)[1]
    return 116.0 * lab_f(y / 100.0) - 16.0


def y_from_lstar(lstar: float) -> float:
    """
    Converts an L* value to a Y value.

    L* in L*a*b* and Y in XYZ measure the same quantity, luminance.

    L* measures perceptual luminance, a linear scale. Y in XYZ measures relative
    luminance, a logarithmic scale.

    :param lstar: L* in L*a*b*
    :return: Y in XYZ
    """
    return 100.0 * lab_invf((lstar + 16.0) / 116.0)


def linearized(rgb_component: int) -> float:
    """
    Linearizes an RGB component.
    :param rgb_component: 0 <= rgb_component <= 255, represents R/G/B channel
    :return: 0.0 <= output <= 100.0, color channel converted to linear RGB space
    """
    normalized = rgb_component / 255.0
    if normalized <= 0.040449936:
        return normalized / 12.92 * 100.0
    return math.pow((normalized + 0.055) / 1.055, 2.4) * 100.0


def delinearized(rgb_component: float) -> int:
    """
    Delinearizes an RGB component.
    :param rgb_component: 0.0 <= rgb_component <= 100.0, represents linear R/G/B channel
    :return: 0 <= output <= 255, color channel converted to regular RGB space
    """
    normalized = rgb_component / 100.0
    if normalized <= 0.0031308:
        delinearized = normalized * 12.92
    else:
        delinearized = 1.055 * math.pow(normalized, 1.0 / 2.4) - 0.055
    return clamp(0, 255, round(delinearized * 255.0))
