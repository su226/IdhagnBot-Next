from typing import Callable

from PIL import Image

from idhagnbot import image, text
from idhagnbot.image.card import Card, CardTab
from idhagnbot.plugins.bilibili_activity.common import fetch_images
from idhagnbot.third_party.bilibili_activity import ExtraGoods


async def format(extra: ExtraGoods) -> Callable[[Card], None]:
  images = await fetch_images(*(i.image for i, _ in zip(extra.goods, range(5))))

  def appender(card: Card) -> None:
    try:
      source = extra.title[extra.title.index("来自") + 2:]
    except ValueError:
      source = "会员购"
    title = f"{source}商品" if len(extra.goods) == 1 else f"{len(extra.goods)} 个{source}商品"
    content = (
      f"{text.escape(extra.goods[0].name)}\n"
      f"<span color='#00aeec'>{text.escape(extra.goods[0].price)}</span> 起"
    ) if len(extra.goods) == 1 else ""
    width = (
      len(images) * 100 + max(len(images) - 1, 0) * 8
      if len(extra.goods) <= 5 else 600
    )
    out_image = Image.new("RGBA", (width, 100))
    for i, im in enumerate(images):
      x = i * 108
      out_image.paste((255, 255, 255), (x, 0, x + 100, 100))
      image.paste(out_image, im.resize((100, 100), image.get_resample()), (x, 0))
    if len(extra.goods) > 5:
      text.paste(out_image, (566, 50), f"+{len(extra.goods) - 5}", "sans", 32, anchor="mm")
    card.add(CardTab(content, title, out_image))

  return appender
