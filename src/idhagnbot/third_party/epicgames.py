from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Optional, TypedDict

from pydantic import BaseModel, TypeAdapter

from idhagnbot import http

__all__ = ["URL_BASE", "Game", "get_free_games"]
API = (
  "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
  "?locale=zh-CN&country=CN&allowCountries=CN"
)
URL_BASE = "https://www.epicgames.com/store/zh-CN/p/"
DISCOUNT_FREE = {"discountType": "PERCENTAGE", "discountPercentage": 0}


class Game(BaseModel):
  start_date: datetime
  end_date: datetime
  title: str
  image: str
  slug: str


class ApiDiscountSetting(TypedDict):
  discountType: str
  discountPercentage: int


class ApiPromotionOffer(TypedDict):
  startDate: Optional[str]
  endDate: Optional[str]
  discountSetting: ApiDiscountSetting


class ApiPromotionOffers(TypedDict):
  promotionalOffers: list[ApiPromotionOffer]


class ApiPromotions(TypedDict):
  promotionalOffers: list[ApiPromotionOffers]
  upcomingPromotionalOffers: list[ApiPromotionOffers]


class ApiKeyImage(TypedDict):
  type: str
  url: str


class ApiMapping(TypedDict):
  pageType: str
  pageSlug: str


class ApiCatalogNs(TypedDict):
  mappings: Optional[list[ApiMapping]]


class ApiElement(TypedDict):
  title: str
  productSlug: Optional[str]
  urlSlug: str
  promotions: Optional[ApiPromotions]
  keyImages: list[ApiKeyImage]
  catalogNs: ApiCatalogNs
  offerMappings: Optional[list[ApiMapping]]


class ApiSearchStore(TypedDict):
  elements: list[ApiElement]


class ApiCatalog(TypedDict):
  searchStore: ApiSearchStore


class ApiData(TypedDict):
  Catalog: ApiCatalog


class ApiResult(TypedDict):
  data: ApiData


ApiResultAdapter = TypeAdapter(ApiResult)


def iter_promotions(game: ApiElement) -> Iterable[ApiPromotionOffer]:
  if game["promotions"]:
    for i in game["promotions"]["promotionalOffers"]:
      yield from i["promotionalOffers"]
    for i in game["promotions"]["upcomingPromotionalOffers"]:
      yield from i["promotionalOffers"]


def get_image(game: ApiElement) -> str:
  for i in game["keyImages"]:
    if i["type"] in ("DieselStoreFrontWide", "OfferImageWide"):
      return i["url"]
  return ""


def iter_mappings(game: ApiElement) -> Iterable[ApiMapping]:
  if game["catalogNs"]["mappings"]:
    yield from game["catalogNs"]["mappings"]
  if game["offerMappings"]:
    yield from game["offerMappings"]


def get_slug(game: ApiElement) -> str:
  for i in iter_mappings(game):
    if i["pageType"] == "productHome":
      return i["pageSlug"]
  return game["productSlug"] or game["urlSlug"]


async def get_free_games() -> list[Game]:
  session = http.get_session()
  async with session.get(API) as response:
    data = ApiResultAdapter.validate_python(await response.json())
  result = list[Game]()
  now_date = datetime.now(timezone.utc)
  for game in data["data"]["Catalog"]["searchStore"]["elements"]:
    for i in iter_promotions(game):
      # Python不支持Z结束，须替换成+00:00
      if i["startDate"] is None or i["endDate"] is None:
        continue
      start_date = datetime.fromisoformat(i["startDate"].replace("Z", "+00:00"))
      end_date = datetime.fromisoformat(i["endDate"].replace("Z", "+00:00"))
      if i["discountSetting"] == DISCOUNT_FREE and start_date < end_date and now_date < end_date:
        result.append(Game(
          start_date=start_date,
          end_date=end_date,
          title=game["title"],
          image=get_image(game),
          slug=get_slug(game),
        ))
        break
  return result
