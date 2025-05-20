from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, TypedDict

from pydantic import TypeAdapter
from typing_extensions import NotRequired

from idhagnbot.http import BROWSER_UA, get_session

__all__ = ["Game", "get_free_games"]
API = (
  "https://egs-platform-service.store.epicgames.com/api/v2/public/discover/home"
  "?count=10&country=CN&locale=zh-CN&platform={platform}&start=0&store=EGS"
)


class ApiMediaItem(TypedDict):
  imageSrc: str


class ApiMedia(TypedDict):
  card16x9: ApiMediaItem


class ApiDiscount(TypedDict):
  discountAmountDisplay: str
  discountEndDate: str


class ApiPurchase(TypedDict):
  purchaseStateEffectiveDate: str
  discount: NotRequired[ApiDiscount]


class ApiContent(TypedDict):
  title: str
  media: ApiMedia
  purchase: list[ApiPurchase]


class ApiOffer(TypedDict):
  content: ApiContent


class ApiData(TypedDict):
  offers: list[ApiOffer]
  type: str


class ApiResult(TypedDict):
  data: list[ApiData]


ApiResultAdapter = TypeAdapter(ApiResult)


@dataclass
class Game:
  start_date: datetime
  end_date: datetime
  name: str
  image: str


async def get_free_games(platform: Literal["android", "ios"]) -> list[Game]:
  async with get_session().get(
    API.format(platform=platform),
    headers={"User-Agent": BROWSER_UA},
  ) as response:
    data = ApiResultAdapter.validate_python(await response.json())
  for topic in data["data"]:
    if topic["type"] == "freeGame":
      offers = topic["offers"]
      break
  else:
    return []
  games: list[Game] = []
  now_date = datetime.now(timezone.utc)
  for offer in offers:
    for purchase in offer["content"]["purchase"]:
      if "discount" in purchase and purchase["discount"]["discountAmountDisplay"] == "-100%":
        start_date = purchase["purchaseStateEffectiveDate"]
        end_date = purchase["discount"]["discountEndDate"]
        start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        if start_date < end_date and now_date < end_date:
          games.append(
            Game(
              start_date=start_date,
              end_date=end_date,
              name=offer["content"]["title"],
              image=offer["content"]["media"]["card16x9"]["imageSrc"],
            ),
          )
          break
  return games
