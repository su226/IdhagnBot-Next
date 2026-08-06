"""
CAM16, a color appearance model. Colors are not just defined by their hexcode, but
rather, a hex code and viewing conditions.

CAM16 instances also have coordinates in the CAM16-UCS space, called J*, a*, b*, or
jstar, astar, bstar in code. CAM16-UCS is included in the CAM16 specification, and
should be used when measuring distances between colors.

In traditional color spaces, a color can be identified solely by the observer's
measurement of the color. Color appearance models such as CAM16 also use information
about the environment where the color was observed, known as the viewing conditions.

For example, white under the traditional assumption of a midday sun white point is
accurately measured as a slightly chromatic blue by CAM16. (roughly, hue 203, chroma 3,
lightness 100)
"""

import math
from dataclasses import dataclass

from idhagnbot.material_color.color_utils import argb_from_xyz, linearized
from idhagnbot.material_color.hct.viewing_conditions import ViewingConditions
from idhagnbot.material_color.math_utils import signum


@dataclass
class Cam16:
    """
    All of the CAM16 dimensions can be calculated from 3 of the dimensions, in the
    following combinations:
      -  {j or q} and {c, m, or s} and hue
      - jstar, astar, bstar
    Prefer using a static method that constructs from 3 of those dimensions. This
    constructor is intended for those methods to use to return all possible dimensions.

    :param hue:
    :param chroma: informally, colorfulness / color intensity. like saturation in HSL,
                   except perceptually accurate.
    :param j: lightness
    :param q: brightness ratio of lightness to white point's lightness
    :param m: colorfulness
    :param s: saturation ratio of chroma to white point's chroma
    :param jstar: CAM16-UCS J coordinate
    :param astar: CAM16-UCS a coordinate
    :param bstar: CAM16-UCS b coordinate
    """

    hue: float
    chroma: float
    j: float
    q: float
    m: float
    s: float
    jstar: float
    astar: float
    bstar: float

    def distance(self, other: Cam16) -> float:
        """
        CAM16 instances also have coordinates in the CAM16-UCS space, called J*, a*, b*,
        or jstar, astar, bstar in code. CAM16-UCS is included in the CAM16
        specification, and is used to measure distances between colors.
        """
        dj = self.jstar - other.jstar
        da = self.astar - other.astar
        db = self.bstar - other.bstar
        de_prime = math.sqrt(dj * dj + da * da + db * db)
        return 1.41 * math.pow(de_prime, 0.63)

    @staticmethod
    def from_argb(
        argb: int,
        viewing_conditions: ViewingConditions = ViewingConditions.DEFAULT,
    ) -> Cam16:
        """
        :param argb: ARGB representation of a color.
        :param viewing_conditions: Information about the environment where the color was
                                   observed.
        :return: CAM16 color.
        """
        red = (argb & 0x00FF0000) >> 16
        green = (argb & 0x0000FF00) >> 8
        blue = argb & 0x000000FF
        red_l = linearized(red)
        green_l = linearized(green)
        blue_l = linearized(blue)
        x = 0.41233895 * red_l + 0.35762064 * green_l + 0.18051042 * blue_l
        y = 0.2126 * red_l + 0.7152 * green_l + 0.0722 * blue_l
        z = 0.01932141 * red_l + 0.11916382 * green_l + 0.95034478 * blue_l
        rc = 0.401288 * x + 0.650173 * y - 0.051461 * z
        gc = -0.250268 * x + 1.204414 * y + 0.045854 * z
        bc = -0.002079 * x + 0.048952 * y + 0.953127 * z
        rd = viewing_conditions.rgb_d[0] * rc
        gd = viewing_conditions.rgb_d[1] * gc
        bd = viewing_conditions.rgb_d[2] * bc
        raf = math.pow((viewing_conditions.fl * abs(rd)) / 100.0, 0.42)
        gaf = math.pow((viewing_conditions.fl * abs(gd)) / 100.0, 0.42)
        baf = math.pow((viewing_conditions.fl * abs(bd)) / 100.0, 0.42)
        ra = (signum(rd) * 400.0 * raf) / (raf + 27.13)
        ga = (signum(gd) * 400.0 * gaf) / (gaf + 27.13)
        ba = (signum(bd) * 400.0 * baf) / (baf + 27.13)
        a = (11.0 * ra + -12.0 * ga + ba) / 11.0
        b = (ra + ga - 2.0 * ba) / 9.0
        u = (20.0 * ra + 20.0 * ga + 21.0 * ba) / 20.0
        p2 = (40.0 * ra + 20.0 * ga + ba) / 20.0
        atan2 = math.atan2(b, a)
        atan_degrees = (atan2 * 180.0) / math.pi
        hue = (
            atan_degrees + 360.0
            if atan_degrees < 0
            else atan_degrees - 360.0
            if atan_degrees >= 360
            else atan_degrees
        )
        hue_radians = (hue * math.pi) / 180.0
        ac = p2 * viewing_conditions.nbb
        j = 100.0 * math.pow(
            ac / viewing_conditions.aw,
            viewing_conditions.c * viewing_conditions.z,
        )
        q = (
            (4.0 / viewing_conditions.c)
            * math.sqrt(j / 100.0)
            * (viewing_conditions.aw + 4.0)
            * viewing_conditions.fl_root
        )
        hue_prime = hue + 360 if hue < 20.14 else hue
        e_hue = 0.25 * (math.cos((hue_prime * math.pi) / 180.0 + 2.0) + 3.8)
        p1 = (50000.0 / 13.0) * e_hue * viewing_conditions.nc * viewing_conditions.ncb
        t = (p1 * math.sqrt(a * a + b * b)) / (u + 0.305)
        alpha = t**0.9 * (1.64 - 0.29**viewing_conditions.n) ** 0.73
        c = alpha * math.sqrt(j / 100.0)
        m = c * viewing_conditions.fl_root
        s = 50.0 * math.sqrt(
            (alpha * viewing_conditions.c) / (viewing_conditions.aw + 4.0),
        )
        jstar = ((1.0 + 100.0 * 0.007) * j) / (1.0 + 0.007 * j)
        mstar = (1.0 / 0.0228) * math.log(1.0 + 0.0228 * m)
        astar = mstar * math.cos(hue_radians)
        bstar = mstar * math.sin(hue_radians)
        return Cam16(hue, c, j, q, m, s, jstar, astar, bstar)

    @staticmethod
    def from_jch(
        j: float,
        c: float,
        h: float,
        viewing_conditions: ViewingConditions = ViewingConditions.DEFAULT,
    ) -> Cam16:
        """
        :param j: CAM16 lightness
        :param c: CAM16 chroma
        :param h: CAM16 hue
        :param viewing_conditions: Information about the environment where the color was
                                   observed.
        """
        q = (
            (4.0 / viewing_conditions.c)
            * math.sqrt(j / 100.0)
            * (viewing_conditions.aw + 4.0)
            * viewing_conditions.fl_root
        )
        m = c * viewing_conditions.fl_root
        alpha = c / math.sqrt(j / 100.0)
        s = 50.0 * math.sqrt(
            (alpha * viewing_conditions.c) / (viewing_conditions.aw + 4.0),
        )
        hue_radians = (h * math.pi) / 180.0
        jstar = ((1.0 + 100.0 * 0.007) * j) / (1.0 + 0.007 * j)
        mstar = (1.0 / 0.0228) * math.log(1.0 + 0.0228 * m)
        astar = mstar * math.cos(hue_radians)
        bstar = mstar * math.sin(hue_radians)
        return Cam16(h, c, j, q, m, s, jstar, astar, bstar)

    def __int__(self) -> int:
        """
        :return: ARGB representation of color, assuming the color was viewed in default
                 viewing conditions, which are near-identical to the default viewing
                 conditions for sRGB.
        """
        return self.to_argb()

    def to_argb(
        self,
        viewing_conditions: ViewingConditions = ViewingConditions.DEFAULT,
    ) -> int:
        """
        :param viewing_conditions: Information about the environment where the color
                                   will be viewed.
        :return: ARGB representation of color
        """
        alpha = (
            0.0
            if self.chroma == 0.0 or self.j == 0.0
            else self.chroma / math.sqrt(self.j / 100.0)
        )
        t = math.pow(
            alpha / math.pow(1.64 - math.pow(0.29, viewing_conditions.n), 0.73),
            1.0 / 0.9,
        )
        h_rad = (self.hue * math.pi) / 180.0
        e_hue = 0.25 * (math.cos(h_rad + 2.0) + 3.8)
        ac = viewing_conditions.aw * (self.j / 100.0) ** (
            1.0 / viewing_conditions.c / viewing_conditions.z
        )
        p1 = e_hue * (50000.0 / 13.0) * viewing_conditions.nc * viewing_conditions.ncb
        p2 = ac / viewing_conditions.nbb
        h_sin = math.sin(h_rad)
        h_cos = math.cos(h_rad)
        gamma = (23.0 * (p2 + 0.305) * t) / (
            23.0 * p1 + 11.0 * t * h_cos + 108.0 * t * h_sin
        )
        a = gamma * h_cos
        b = gamma * h_sin
        ra = (460.0 * p2 + 451.0 * a + 288.0 * b) / 1403.0
        ga = (460.0 * p2 - 891.0 * a - 261.0 * b) / 1403.0
        ba = (460.0 * p2 - 220.0 * a - 6300.0 * b) / 1403.0
        rc_base = max(0, (27.13 * abs(ra)) / (400.0 - abs(ra)))
        rc = (
            signum(ra) * (100.0 / viewing_conditions.fl) * math.pow(rc_base, 1.0 / 0.42)
        )
        gc_base = max(0, (27.13 * abs(ga)) / (400.0 - abs(ga)))
        gc = (
            signum(ga) * (100.0 / viewing_conditions.fl) * math.pow(gc_base, 1.0 / 0.42)
        )
        bc_base = max(0, (27.13 * abs(ba)) / (400.0 - abs(ba)))
        bc = (
            signum(ba) * (100.0 / viewing_conditions.fl) * math.pow(bc_base, 1.0 / 0.42)
        )
        rf = rc / viewing_conditions.rgb_d[0]
        gf = gc / viewing_conditions.rgb_d[1]
        bf = bc / viewing_conditions.rgb_d[2]
        x = 1.86206786 * rf - 1.01125463 * gf + 0.14918677 * bf
        y = 0.38752654 * rf + 0.62144744 * gf - 0.00897398 * bf
        z = -0.01584150 * rf - 0.03412294 * gf + 1.04996444 * bf
        return argb_from_xyz(x, y, z)
