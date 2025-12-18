from dataclasses import dataclass
from typing import (
  Generic,
  Literal,
  Optional,
  Protocol,
  TypeVar,
)

from pydantic import TypeAdapter
from typing_extensions import NotRequired, TypedDict

from idhagnbot.http import BROWSER_UA, get_session
from idhagnbot.third_party.bilibili_auth import get_cookie, validate_result

TContent_co = TypeVar("TContent_co", covariant=True)
TExtra_co = TypeVar("TExtra_co", covariant=True)

LIST_API = (
  "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
  "?host_mid={uid}&offset={offset}&features=itemOpusStyle"
)
DETAIL_API = (
  "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail?id={id}&features=itemOpusStyle"
)
LIST_API_OLD = (
  "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history"
  "?host_uid={uid}&offset_dynamic_id={offset}"
)
DETAIL_API_OLD = (
  "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/get_dynamic_detail?dynamic_id={id}"
)


# 20251209: 获取空间的 API 采用了新的模型（部分 ID 改为字符串；部分字段必定出现但可能为 null）
# 但获取详情的 API 依然是旧的模型（上述 ID 仍为整数；上述字段可能不出现）


class ApiAuthorModule(TypedDict):
  mid: int
  name: str
  face: str
  pub_ts: str | int
  label: str


class ApiVote(TypedDict):
  vote_id: str | int
  uid: str | int
  desc: str
  join_num: str | int | None
  end_time: str | int


class ApiUgc(TypedDict):
  id_str: str
  title: str
  desc_second: str
  duration: str
  cover: str


class ApiReserveButtonData(TypedDict):
  disable: NotRequired[int | None]


class ApiReserveButton(TypedDict):
  type: int
  uncheck: ApiReserveButtonData


class ApiReserveDesc(TypedDict):
  text: str


class ApiReserve(TypedDict):
  stype: int
  button: ApiReserveButton
  rid: int
  up_mid: int
  title: str
  desc1: ApiReserveDesc
  desc2: ApiReserveDesc
  reserve_total: int
  jump_url: str


class ApiGoodsItem(TypedDict):
  id: int
  name: str
  brief: str
  price: str
  jump_url: str
  cover: str


class ApiGoods(TypedDict):
  head_text: str
  items: list[ApiGoodsItem]


class ApiAdditionalCommon(TypedDict):
  head_text: str
  title: str
  desc1: str
  desc2: str
  cover: str


class ApiAdditional(TypedDict):
  type: str
  vote: NotRequired[ApiVote | None]
  ugc: NotRequired[ApiUgc | None]
  reserve: NotRequired[ApiReserve | None]
  goods: NotRequired[ApiGoods | None]
  common: NotRequired[ApiAdditionalCommon | None]


class ApiEmoji(TypedDict):
  icon_url: str


class ApiRichTextNode(TypedDict):
  type: str
  text: str
  emoji: NotRequired[ApiEmoji | None]
  rid: NotRequired[str | None]


class ApiDesc(TypedDict):
  text: str
  rich_text_nodes: list[ApiRichTextNode]


class ApiDrawItem(TypedDict):
  src: str
  width: int
  height: int
  size: float


class ApiDraw(TypedDict):
  items: list[ApiDrawItem]


class ApiArchiveStat(TypedDict):
  danmaku: str
  play: str


class ApiArchive(TypedDict):
  aid: str
  bvid: str
  cover: str
  desc: str
  duration_text: str
  stat: ApiArchiveStat
  title: str


class ApiArticle(TypedDict):
  id: int
  title: str
  desc: str
  covers: list[str]
  label: str


class ApiMusic(TypedDict):
  id: int
  title: str
  cover: str
  label: str


class ApiPgc(TypedDict):
  season_id: str | int
  epid: str | int
  title: str
  cover: str
  stat: ApiArchiveStat


class ApiBadge(TypedDict):
  text: str


class ApiCommon(TypedDict):
  cover: str
  title: str
  desc: str
  badge: ApiBadge


class ApiLive(TypedDict):
  id: str | int
  title: str
  desc_first: str
  cover: str
  live_state: int


class ApiLiveRcmd(TypedDict):
  content: str


class ApiWatchedShow(TypedDict):
  num: int


class ApiLivePlayInfo(TypedDict):
  live_id: str
  room_id: int
  uid: int
  title: str
  cover: str
  area_name: str
  area_id: int
  parent_area_name: str
  parent_area_id: int
  live_start_time: int
  watched_show: ApiWatchedShow


class ApiLiveRcmdData(TypedDict):
  live_play_info: ApiLivePlayInfo


class ApiCourse(TypedDict):
  id: str | int
  title: str
  sub_title: str
  desc: str
  cover: str


class ApiNone(TypedDict):
  tips: str


class ApiOpusPic(TypedDict):
  url: str
  width: int
  height: int
  size: float | None


class ApiOpus(TypedDict):
  title: str | None
  summary: ApiDesc
  pics: list[ApiOpusPic]


class ApiBlocked(TypedDict):
  hint_message: str


class ApiMajor(TypedDict):
  type: str
  draw: NotRequired[ApiDraw | None]
  archive: NotRequired[ApiArchive | None]
  article: NotRequired[ApiArticle | None]
  music: NotRequired[ApiMusic | None]
  pgc: NotRequired[ApiPgc | None]
  common: NotRequired[ApiCommon | None]
  live: NotRequired[ApiLive | None]
  live_rcmd: NotRequired[ApiLiveRcmd | None]
  courses: NotRequired[ApiCourse | None]
  none: NotRequired[ApiNone | None]
  opus: NotRequired[ApiOpus | None]
  blocked: NotRequired[ApiBlocked | None]


class ApiTopic(TypedDict):
  id: str | int
  name: str


class ApiDynamicModule(TypedDict):
  additional: ApiAdditional | None
  desc: ApiDesc | None
  major: ApiMajor | None
  topic: ApiTopic | None


class ApiStatItem(TypedDict):
  count: int


class ApiStatModule(TypedDict):
  comment: ApiStatItem
  forward: ApiStatItem
  like: ApiStatItem


class ApiTagModule(TypedDict):
  text: str


class ApiModules(TypedDict):
  module_author: ApiAuthorModule
  module_dynamic: ApiDynamicModule
  module_stat: NotRequired[ApiStatModule | None]
  module_tag: NotRequired[ApiTagModule | None]


class ApiDynamic(TypedDict):
  id_str: str | None
  modules: ApiModules
  type: str
  orig: NotRequired["ApiDynamic | None"]


class ApiSpaceResult(TypedDict):
  offset: str
  has_more: bool
  items: list[ApiDynamic]


class ApiDetailResult(TypedDict):
  item: ApiDynamic


async def fetch(uid: int, offset: str = "") -> tuple[list[ApiDynamic], str | None]:
  http = get_session()
  headers = {
    "Cookie": get_cookie(),
    "User-Agent": BROWSER_UA,
  }
  async with http.get(LIST_API.format(uid=uid, offset=offset), headers=headers) as response:
    data = validate_result(await response.json(), ApiSpaceResult)
  next_offset = data["offset"] if data["has_more"] else None
  return data["items"], next_offset


async def get(activity_id: int) -> ApiDynamic:
  http = get_session()
  headers = {
    "Referer": f"https://t.bilibili.com/{activity_id}",
    "Cookie": get_cookie(),
    "User-Agent": BROWSER_UA,
  }
  async with http.get(DETAIL_API.format(id=activity_id), headers=headers) as response:
    data = validate_result(await response.json(), ApiDetailResult)
  return data["item"]


@dataclass
class RichTextNode:
  text: str


class RichTextText(RichTextNode):
  pass


class RichTextOther(RichTextNode):
  pass


@dataclass
class RichTextEmotion(RichTextNode):
  url: str


@dataclass
class RichTextLottery(RichTextNode):
  rid: int


RichText = list[RichTextNode]


def parse_richtext(text: list[ApiRichTextNode]) -> RichText:
  nodes: RichText = []
  for node in text:
    if node["type"] == "RICH_TEXT_NODE_TYPE_TEXT":
      nodes.append(RichTextText(node["text"]))
    elif node["type"] == "RICH_TEXT_NODE_TYPE_EMOJI":
      emoji = node.get("emoji")
      assert emoji
      nodes.append(RichTextEmotion(node["text"], emoji["icon_url"]))
    elif node["type"] == "RICH_TEXT_NODE_TYPE_LOTTERY":
      rid = node.get("rid")
      assert rid
      nodes.append(RichTextLottery(node["text"], int(rid)))
    else:
      nodes.append(RichTextOther(node["text"]))
  return nodes


class ContentParser(Protocol[TContent_co]):
  @staticmethod
  def parse(item: ApiDynamic) -> TContent_co: ...


@dataclass
class ContentText(ContentParser["ContentText"]):
  text: str
  richtext: RichText

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentText":
    module = item["modules"]["module_dynamic"]
    desc = module["desc"]
    assert desc
    return ContentText(desc["text"], parse_richtext(desc["rich_text_nodes"]))


@dataclass
class Image:
  src: str
  width: int
  height: int
  size: float


@dataclass
class ContentImage(ContentParser["ContentImage"]):
  text: str
  richtext: RichText
  images: list[Image]

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentImage":
    module = item["modules"]["module_dynamic"]
    if major := module["major"]:
      draw = major.get("draw")
      assert draw
      images = [
        Image(
          image["src"],
          image["width"],
          image["height"],
          image["size"],
        )
        for image in draw["items"]
      ]
    else:
      images = []
    desc = module["desc"]
    if desc:
      text = desc["text"]
      richtext = parse_richtext(desc["rich_text_nodes"])
    else:
      text = ""
      richtext = []
    return ContentImage(text, richtext, images)


@dataclass
class ContentOpus(ContentParser["ContentOpus"]):
  title: str
  text: str
  richtext: RichText
  images: list[Image]

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentOpus":
    major = item["modules"]["module_dynamic"]["major"]
    assert major
    opus = major.get("opus")
    assert opus
    desc = opus["summary"]
    return ContentOpus(
      opus["title"] or "",
      desc["text"],
      parse_richtext(desc["rich_text_nodes"]),
      [
        Image(
          image["url"],
          image["width"],
          image["height"],
          image["size"] or 0,
        )
        for image in opus["pics"]
      ],
    )


@dataclass
class ContentVideo(ContentParser["ContentVideo"]):
  text: str
  richtext: RichText  # 动态视频有富文本
  avid: int
  bvid: str
  title: str
  desc: str
  cover: str
  duration: int
  formatted_view: str
  formatted_danmaku: str

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentVideo":
    module = item["modules"]["module_dynamic"]
    major = module["major"]
    assert major
    video = major.get("archive")
    assert video
    duration_text = video["duration_text"]
    try:
      duration_seg = duration_text.split(":")
      if len(duration_seg) == 2:
        h = 0
        m, s = duration_seg
      else:
        h, m, s = duration_seg
      duration = int(h) * 3600 + int(m) * 60 + int(s)
    except ValueError:
      duration = -1
    if desc := module.get("desc"):
      text = desc["text"]
      richtext = parse_richtext(desc["rich_text_nodes"])
    else:
      text = ""
      richtext = []
    return ContentVideo(
      text,
      richtext,
      int(video["aid"]),
      video["bvid"],
      video["title"],
      video["desc"],
      video["cover"],
      duration,
      video["stat"]["play"],
      video["stat"]["danmaku"],
    )


@dataclass
class ContentArticle(ContentParser["ContentArticle"]):
  """
  专栏
  https://www.bilibili.com/read/cv<ID>
  """

  id: int
  title: str
  desc: str
  covers: list[str]
  formatted_view: str

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentArticle":
    major = item["modules"]["module_dynamic"]["major"]
    assert major
    article = major.get("article")
    assert article
    return ContentArticle(
      article["id"],
      article["title"],
      article["desc"],
      article["covers"],
      article["label"],
    )


@dataclass
class ContentAudio(ContentParser["ContentAudio"]):
  """
  音频
  https://www.bilibili.com/audio/au<ID>
  """

  id: int
  title: str
  desc: str
  cover: str
  label: str

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentAudio":
    module = item["modules"]["module_dynamic"]
    desc = module["desc"]
    assert desc
    major = module["major"]
    assert major
    audio = major.get("music")
    assert audio
    return ContentAudio(
      audio["id"],
      audio["title"],
      desc["text"],
      audio["cover"],
      audio["label"],
    )


@dataclass
class ContentPGC(ContentParser["ContentPGC"]):
  """
  番剧、电视剧、电影、纪录片等 PGC（Professional Generated Content，专业生产内容，与之相对的是
  User Generated Content，用户生产内容，就是 UP 主上传的视频、专栏等）
  https://www.bilibili.com/bangumi/media/md<SSID> # 介绍页
  https://www.bilibili.com/bangumi/play/ss<SSID> # 播放第一集
  https://www.bilibili.com/bangumi/play/ep<EPID> # 播放指定集
  这种动态只会出现在转发里
  """

  ssid: int
  epid: int
  season_name: str
  episode_name: str
  season_cover: str
  episode_cover: str
  label: str
  formatted_view: str
  formatted_danmaku: str

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentPGC":
    modules = item["modules"]
    author = modules["module_author"]
    major = modules["module_dynamic"]["major"]
    assert major
    pgc = major.get("pgc")
    assert pgc
    return ContentPGC(
      int(pgc["season_id"]),
      int(pgc["epid"]),
      author["name"],
      pgc["title"],
      author["face"],
      pgc["cover"],
      author["label"],
      pgc["stat"]["play"],
      pgc["stat"]["danmaku"],
    )


@dataclass
class ContentCommon(ContentParser["ContentCommon"]):
  """通用方卡（用于番剧评分、大会员活动等）和通用竖卡（暂时不明）"""

  text: str
  richtext: RichText
  cover: str
  title: str
  desc: str
  badge: str
  vertical: bool

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentCommon":
    module = item["modules"]["module_dynamic"]
    desc = module["desc"]
    assert desc
    major = module["major"]
    assert major
    common = major.get("common")
    assert common
    return ContentCommon(
      desc["text"],
      parse_richtext(desc["rich_text_nodes"]),
      common["cover"],
      common["title"],
      common["desc"],
      common["badge"]["text"],
      item["type"] == "DYNAMIC_TYPE_COMMON_VERTICAL",
    )


@dataclass
class ContentLive(ContentParser["ContentLive"]):
  """
  直播间
  这种动态只会出现在转发里
  """

  id: int
  title: str
  category: str
  cover: str
  streaming: bool

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentLive":
    major = item["modules"]["module_dynamic"]["major"]
    assert major
    live = major.get("live")
    assert live
    return ContentLive(
      int(live["id"]),
      live["title"],
      live["desc_first"],
      live["cover"],
      bool(live["live_state"]),
    )


@dataclass
class ContentLiveRcmd(ContentParser["ContentLiveRcmd"]):
  """
  直播推荐/直播场次
  这种动态可能出现在转发里，也可能出现在动态里
  下播之后对应动态也会消失
  """

  live_id: int
  room_id: int
  uid: int
  title: str
  cover: str
  category: str
  category_id: int
  parent_category: str
  parent_category_id: int
  start_time: int
  watching: int

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentLiveRcmd":
    major = item["modules"]["module_dynamic"]["major"]
    assert major
    live_rcmd = major.get("live_rcmd")
    assert live_rcmd
    live = TypeAdapter(ApiLiveRcmdData).validate_json(live_rcmd["content"])["live_play_info"]
    return ContentLiveRcmd(
      int(live["live_id"]),
      live["room_id"],
      live["uid"],
      live["title"],
      live["cover"],
      live["area_name"],
      live["area_id"],
      live["parent_area_name"],
      live["parent_area_id"],
      live["live_start_time"],
      live["watched_show"]["num"],
    )


@dataclass
class ContentCourse(ContentParser["ContentCourse"]):
  """
  课程
  这种动态只会出现在转发里
  """

  id: int
  title: str
  desc: str
  stat: str
  cover: str

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentCourse":
    major = item["modules"]["module_dynamic"]["major"]
    assert major
    course = major.get("courses")
    assert course
    return ContentCourse(
      int(course["id"]),
      course["title"],
      course["sub_title"],
      course["desc"],
      course["cover"],
    )


@dataclass
class ContentPlaylist(ContentParser["ContentPlaylist"]):
  """
  合集（播放列表）
  这种动态只会出现在转发里
  """

  id: int
  title: str
  stat: str
  cover: str

  # JSON API 获取不到转发合集，所以只有 grpc_parse
  @staticmethod
  def parse(item: ApiDynamic) -> "ContentPlaylist":
    raise NotImplementedError


@dataclass
class ContentForward(ContentParser["ContentForward"]):
  text: str
  richtext: RichText
  activity: Optional["Activity[object, object]"]
  error_text: str

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentForward":
    desc = item["modules"]["module_dynamic"]["desc"]
    assert desc
    orig = item.get("orig")
    assert orig
    if orig["type"] == "DYNAMIC_TYPE_NONE":
      original = None  # 源动态失效
      major = orig["modules"]["module_dynamic"]["major"]
      assert major
      none = major.get("none")
      assert none
      error_text = none["tips"]
    else:
      original = Activity.parse(orig)
      error_text = ""
    return ContentForward(
      desc["text"],
      parse_richtext(desc["rich_text_nodes"]),
      original,
      error_text,
    )


@dataclass
class ContentBlocked(ContentParser["ContentBlocked"]):
  """
  无法查看的充电动态
  """

  message: str

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentBlocked":
    major = item["modules"]["module_dynamic"]["major"]
    assert major
    blocked = major.get("blocked")
    assert blocked
    return ContentBlocked(blocked["hint_message"])


class ContentUnknown(ContentParser["ContentUnknown"]):
  @staticmethod
  def parse(item: ApiDynamic) -> "ContentUnknown":
    return ContentUnknown()


CONTENT_TYPES: dict[str, type[ContentParser[object]]] = {
  "WORD": ContentText,
  "DRAW": ContentImage,
  "AV": ContentVideo,
  "ARTICLE": ContentArticle,
  "MUSIC": ContentAudio,
  "PGC": ContentPGC,
  "COMMON_SQUARE": ContentCommon,
  "COMMON_VERTICAL": ContentCommon,
  "COURSES_SEASON": ContentCourse,
  "LIVE": ContentLive,
  "LIVE_RCMD": ContentLiveRcmd,
  # JSON API 获取不到转发合集
  "FORWARD": ContentForward,
}


class ExtraParser(Protocol[TExtra_co]):
  @staticmethod
  def parse(item: ApiAdditional) -> TExtra_co:
    raise NotImplementedError


@dataclass
class ExtraVote(ExtraParser["ExtraVote"]):
  id: int
  uid: int
  title: str
  count: int
  end: int

  @staticmethod
  def parse(item: ApiAdditional) -> "ExtraVote":
    vote = item.get("vote")
    assert vote
    return ExtraVote(
      int(vote["vote_id"]),
      int(vote["uid"]),
      vote["desc"],
      int(vote["join_num"] or 0),  # 0 人时是 null
      int(vote["end_time"]),
    )


@dataclass
class ExtraVideo(ExtraParser["ExtraVideo"]):
  id: int
  title: str
  desc: str
  duration: str
  cover: str

  @staticmethod
  def parse(item: ApiAdditional) -> "ExtraVideo":
    video = item.get("ugc")
    assert video
    return ExtraVideo(
      int(video["id_str"]),
      video["title"],
      video["desc_second"],
      video["duration"],
      video["cover"],
    )


@dataclass
class ExtraReserve(ExtraParser["ExtraReserve"]):
  id: int
  uid: int
  title: str
  desc: str
  desc2: str
  count: int
  link_text: str
  link_url: str
  type: Literal["video", "live"]
  status: Literal["reserving", "streaming", "expired"]
  content_url: str

  @staticmethod
  def parse(item: ApiAdditional) -> "ExtraReserve":
    reserve = item.get("reserve")
    assert reserve
    reserve_type = "video" if reserve["stype"] == 1 else "live"
    button = reserve["button"]
    if reserve_type == "live":
      if button["type"] == 1:
        status = "streaming"
      else:
        status = "expired" if "disable" in button["uncheck"] else "reserving"
    else:
      status = "expired" if button["type"] == 1 else "reserving"
    desc3 = reserve.get("desc3", None)
    return ExtraReserve(
      reserve["rid"],
      reserve["up_mid"],
      reserve["title"],
      reserve["desc1"]["text"],
      reserve["desc2"]["text"],
      reserve["reserve_total"],
      desc3["text"] if desc3 else "",
      desc3["jump_url"] if desc3 else "",
      reserve_type,
      status,
      reserve["jump_url"],
    )


@dataclass
class Goods:
  id: int
  name: str
  brief: str
  price: str
  url: str
  image: str


@dataclass
class ExtraGoods(ExtraParser["ExtraGoods"]):
  title: str
  goods: list[Goods]

  @staticmethod
  def parse(item: ApiAdditional) -> "ExtraGoods":
    goods = item.get("goods")
    assert goods
    return ExtraGoods(
      goods["head_text"],
      [
        Goods(i["id"], i["name"], i["brief"], i["price"], i["jump_url"], i["cover"])
        for i in goods["items"]
      ],
    )


@dataclass
class ExtraCommon(ExtraParser["ExtraCommon"]):
  head_text: str
  title: str
  cover: str
  desc1: str
  desc2: str

  @staticmethod
  def parse(item: ApiAdditional) -> "ExtraCommon":
    common = item.get("common")
    assert common
    return ExtraCommon(
      common["head_text"],
      common["title"],
      common["cover"],
      common["desc1"],
      common["desc2"],
    )


class ExtraUnknown(ExtraParser["ExtraUnknown"]):
  @staticmethod
  def parse(item: ApiAdditional) -> "ExtraUnknown":
    return ExtraUnknown()


EXTRA_TYPES: dict[str, type[ExtraParser[object]]] = {
  "VOTE": ExtraVote,
  "UGC": ExtraVideo,
  "RESERVE": ExtraReserve,
  "GOODS": ExtraGoods,
  "COMMON": ExtraCommon,
}


@dataclass
class Stat:
  repost: int
  like: int
  reply: int


@dataclass
class Extra(Generic[TExtra_co]):
  type: str
  value: TExtra_co


@dataclass
class Topic:
  id: int
  name: str


@dataclass
class Activity(Generic[TContent_co, TExtra_co]):
  uid: int
  name: str
  avatar: str
  id: int
  top: bool
  type: str
  content: TContent_co
  stat: Stat | None
  time: int
  extra: Extra[TExtra_co] | None
  topic: Topic | None

  @staticmethod
  def parse(item: ApiDynamic) -> "Activity[object, object]":
    modules = item["modules"]
    author_module = modules["module_author"]
    tag = modules.get("module_tag")
    top = bool(tag) and tag["text"] == "置顶"
    stat = None
    if stat_module := modules.get("module_stat"):
      stat = Stat(
        stat_module["forward"]["count"],
        stat_module["like"]["count"],
        stat_module["comment"]["count"],
      )
    content_type = item["type"].removeprefix("DYNAMIC_TYPE_")
    dynamic_module = modules["module_dynamic"]
    major = dynamic_module["major"]
    if major and major["type"] == "MAJOR_TYPE_BLOCKED":
      content_cls = ContentBlocked
    elif major and major["type"] == "MAJOR_TYPE_OPUS":
      content_cls = ContentOpus
    else:
      content_cls = CONTENT_TYPES.get(content_type, ContentUnknown)
    extra = None
    if (additional := dynamic_module["additional"]) is not None:
      extra_type = additional["type"].removeprefix("ADDITIONAL_TYPE_")
      extra_cls = EXTRA_TYPES.get(extra_type, ExtraUnknown)
      extra = Extra(extra_type, extra_cls.parse(additional))
    topic = None
    if (raw_topic := dynamic_module["topic"]) is not None:
      topic = Topic(int(raw_topic["id"]), raw_topic["name"])
    return Activity(
      author_module["mid"],
      author_module["name"],
      author_module["face"],
      int(item["id_str"] or 0),
      top,
      content_type,
      content_cls.parse(item),
      stat,
      int(author_module["pub_ts"]),
      extra,
      topic,
    )


ActivityText = Activity[ContentText, TExtra_co]
ActivityImage = Activity[ContentImage, TExtra_co]
ActivityOpus = Activity[ContentOpus, TExtra_co]
ActivityArticle = Activity[ContentArticle, TExtra_co]
ActivityVideo = Activity[ContentVideo, TExtra_co]
ActivityAudio = Activity[ContentAudio, TExtra_co]
ActivityPGC = Activity[ContentPGC, TExtra_co]
ActivityCommon = Activity[ContentCommon, TExtra_co]
ActivityForward = Activity[ContentForward, TExtra_co]
ActivityLive = Activity[ContentLive, TExtra_co]
ActivityLiveRcmd = Activity[ContentLiveRcmd, TExtra_co]
ActivityCourse = Activity[ContentCourse, TExtra_co]
ActivityPlaylist = Activity[ContentPlaylist, TExtra_co]
ActivityBlocked = Activity[ContentBlocked, TExtra_co]
