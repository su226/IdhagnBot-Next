from io import BytesIO

from anyio.to_thread import run_sync
from PIL import Image

from idhagnbot.asyncio import gather_map
from idhagnbot.http import get_session
from idhagnbot.image import get_scale_resample
from idhagnbot.image.card import CONTENT_WIDTH, PADDING, WIDTH, Render
from idhagnbot.text import RichText as RichTextRender
from idhagnbot.text import escape, render

from . import RichText, RichTextEmotion, RichTextText, Topic

EMOTION_SIZE = 48


async def fetch_emotion(url: str) -> Image.Image:
  async with get_session().get(url) as response:
    data = await response.read()
  return await run_sync(
    lambda: Image.open(BytesIO(data)).resize((EMOTION_SIZE, EMOTION_SIZE), get_scale_resample()),
  )


async def fetch_emotions(richtext: RichText) -> dict[str, Image.Image]:
  return await gather_map(
    {node.url: fetch_emotion(node.url) for node in richtext if isinstance(node, RichTextEmotion)},
  )


class CardTopic(Render):
  def __init__(self, topic: Topic | None) -> None:
    self._im = None
    if topic:
      self._im = render("#" + topic.name, "sans", 32, color=0x008AC5, box=CONTENT_WIDTH)

  def get_width(self) -> int:
    return WIDTH

  def get_height(self) -> int:
    return self._im.height if self._im else 0

  def render(self, dst: Image.Image, x: int, y: int) -> None:
    if self._im:
      dst.paste(self._im, (x + PADDING, y), self._im)


class CardRichText(Render):
  def __init__(
    self,
    richtext: RichText,
    emotions: dict[str, Image.Image],
    size: int,
    lines: int,
  ) -> None:
    render = RichTextRender().set_font("sans", size)
    render.set_width(CONTENT_WIDTH).set_height(-lines).set_ellipsize("end")
    for node in richtext:
      if isinstance(node, RichTextText):
        render.append(node.text)
      elif isinstance(node, RichTextEmotion):
        render.append_image(emotions[node.url])
      else:
        render.append_markup(f"<span color='#008ac5'>{escape(node.text)}</span>")
    self._im = render.render()

  def get_width(self) -> int:
    return WIDTH

  def get_height(self) -> int:
    return self._im.height

  def render(self, dst: Image.Image, x: int, y: int) -> None:
    dst.paste(self._im, (x + PADDING, y), self._im)
