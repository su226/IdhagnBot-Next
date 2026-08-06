# 修改自 https://github.com/avanisubbiah/material-color-utilities-python
# 移除了不必要的 import，增加类型注解

from PIL import Image

from idhagnbot.image import load
from idhagnbot.material_color import score
from idhagnbot.material_color.color_utils import argb_from_rgb
from idhagnbot.material_color.quantize import quantizer_celebi


def source_color_from_image(image: Image.Image) -> int:
    """
    Get the source color from an image.
    :param image: The image element
    :return: Source color - the color most suitable for creating a UI theme
    """
    if image.has_transparency_data:
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        px = load(image, tuple[int, int, int, int])
        pixels: list[int] = []
        for x in range(image.width):
            for y in range(image.height):
                r, g, b, a = px[x, y]
                if a < 255:
                    continue
                argb = argb_from_rgb(r, g, b)
                pixels.append(argb)
    else:
        if image.mode != "RGB":
            image = image.convert("RGB")
        px = load(image, tuple[int, int, int])
        pixels: list[int] = []
        for x in range(image.width):
            for y in range(image.height):
                r, g, b = px[x, y]
                argb = argb_from_rgb(r, g, b)
                pixels.append(argb)

    result = quantizer_celebi.quantize(pixels, 128)
    ranked = score.score(result)
    return ranked[0]
