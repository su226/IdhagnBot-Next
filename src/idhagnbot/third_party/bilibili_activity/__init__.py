from dataclasses import dataclass
from typing import (
  Generic,
  Literal,
  Optional,
  Protocol,
  TypedDict,
  TypeVar,
)

from pydantic import TypeAdapter
from typing_extensions import NotRequired

from idhagnbot.http import BROWSER_UA, get_session
from idhagnbot.third_party.bilibili_auth import get_cookie, validate_result

TContent = TypeVar("TContent", covariant=True)
TExtra = TypeVar("TExtra", covariant=True)

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


class ApiAuthorModule(TypedDict):
  mid: int
  name: str
  face: str
  pub_ts: int
  label: str


class ApiVote(TypedDict):
  vote_id: int
  uid: int
  desc: str
  join_num: Optional[int]
  end_time: int


class ApiUgc(TypedDict):
  id_str: str
  title: str
  desc_second: str
  duration: str
  cover: str


class ApiReserveButtonData(TypedDict):
  disable: NotRequired[str]


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


class ApiAdditional(TypedDict):
  type: str
  vote: NotRequired[ApiVote]
  ugc: NotRequired[ApiUgc]
  reserve: NotRequired[ApiReserve]
  goods: NotRequired[ApiGoods]


class ApiEmoji(TypedDict):
  icon_url: str


class ApiRichTextNode(TypedDict):
  type: str
  text: str
  emoji: NotRequired[ApiEmoji]
  rid: NotRequired[str]


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
  season_id: int
  epid: int
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
  id: int
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
  id: int
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
  size: float


class ApiOpus(TypedDict):
  title: Optional[str]
  summary: ApiDesc
  pics: list[ApiOpusPic]


class ApiMajor(TypedDict):
  type: str
  draw: NotRequired[ApiDraw]
  archive: NotRequired[ApiArchive]
  article: NotRequired[ApiArticle]
  music: NotRequired[ApiMusic]
  pgc: NotRequired[ApiPgc]
  common: NotRequired[ApiCommon]
  live: NotRequired[ApiLive]
  live_rcmd: NotRequired[ApiLiveRcmd]
  courses: NotRequired[ApiCourse]
  none: NotRequired[ApiNone]
  opus: NotRequired[ApiOpus]


class ApiTopic(TypedDict):
  id: int
  name: str


class ApiDynamicModule(TypedDict):
  additional: Optional[ApiAdditional]
  desc: Optional[ApiDesc]
  major: Optional[ApiMajor]
  topic: Optional[ApiTopic]


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
  module_stat: NotRequired[ApiStatModule]
  module_tag: NotRequired[ApiTagModule]


class ApiDynamic(TypedDict):
  id_str: Optional[str]
  modules: ApiModules
  type: str
  orig: NotRequired["ApiDynamic"]


class ApiSpaceResult(TypedDict):
  offset: str
  has_more: bool
  items: list[ApiDynamic]


class ApiDetailResult(TypedDict):
  item: ApiDynamic


async def fetch(uid: int, offset: str = "") -> tuple[list[ApiDynamic], Optional[str]]:
  http = get_session()
  headers = {
    "Cookie": get_cookie(),
    "User-Agent": BROWSER_UA,
  }
  async with http.get(LIST_API.format(uid=uid, offset=offset), headers=headers) as response:
    data = validate_result(await response.json(), ApiSpaceResult)
  next_offset = data["offset"] if data["has_more"] else None
  return data["items"], next_offset


async def get(id: int) -> ApiDynamic:
  http = get_session()
  headers = {
    "Referer": f"https://t.bilibili.com/{id}",
    "Cookie": get_cookie(),
    "User-Agent": BROWSER_UA,
  }
  async with http.get(DETAIL_API.format(id=id), headers=headers) as response:
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
      assert "emoji" in node
      nodes.append(RichTextEmotion(node["text"], node["emoji"]["icon_url"]))
    elif node["type"] == "RICH_TEXT_NODE_TYPE_LOTTERY":
      assert "rid" in node
      nodes.append(RichTextLottery(node["text"], int(node["rid"])))
    else:
      nodes.append(RichTextOther(node["text"]))
  return nodes


class ContentParser(Protocol[TContent]):
  @staticmethod
  def parse(item: ApiDynamic) -> TContent: ...


@dataclass
class ContentText(ContentParser["ContentText"]):
  title: str
  text: str
  richtext: RichText

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentText":
    module = item["modules"]["module_dynamic"]
    major = module["major"]
    if major and "opus" in major:
      opus = major["opus"]
      title = opus["title"] or ""
      desc = opus["summary"]
    else:
      title = ""
      desc = module["desc"]
      assert desc
    return ContentText(title, desc["text"], parse_richtext(desc["rich_text_nodes"]))


@dataclass
class Image:
  src: str
  width: int
  height: int
  size: float


@dataclass
class ContentImage(ContentParser["ContentImage"]):
  title: str
  text: str
  richtext: RichText
  images: list[Image]

  @staticmethod
  def parse(item: ApiDynamic) -> "ContentImage":
    module = item["modules"]["module_dynamic"]
    major = module["major"]
    assert major
    if "opus" in major:
      opus = major["opus"]
      title = opus["title"] or ""
      desc = opus["summary"]
      pics = [
        Image(
          image["url"],
          image["width"],
          image["height"],
          image["size"],
        )
        for image in opus["pics"]
      ]
    else:
      title = ""
      desc = module["desc"]
      assert desc
      assert "draw" in major
      pics = [
        Image(
          image["src"],
          image["width"],
          image["height"],
          image["size"],
        )
        for image in major["draw"]["items"]
      ]
    return ContentImage(title, desc["text"], parse_richtext(desc["rich_text_nodes"]), pics)


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
    assert "archive" in major
    video = major["archive"]
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
    desc = module["desc"]
    if desc:
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
    assert "article" in major
    major = major["article"]
    return ContentArticle(
      major["id"],
      major["title"],
      major["desc"],
      major["covers"],
      major["label"],
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
    major = module["major"]
    assert desc
    assert major
    assert "music" in major
    audio = major["music"]
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
    assert "pgc" in major
    pgc = major["pgc"]
    return ContentPGC(
      pgc["season_id"],
      pgc["epid"],
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
    major = module["major"]
    desc = module["desc"]
    assert desc
    assert major
    assert "common" in major
    common = major["common"]
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
    assert "live" in major
    live = major["live"]
    return ContentLive(
      live["id"],
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
    assert "live_rcmd" in major
    live = TypeAdapter(ApiLiveRcmdData).validate_json(major["live_rcmd"]["content"])
    live = live["live_play_info"]
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
    assert "courses" in major
    course = major["courses"]
    return ContentCourse(
      course["id"],
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
    assert "orig" in item
    assert desc
    if item["orig"]["type"] == "DYNAMIC_TYPE_NONE":
      original = None  # 源动态失效
      major = item["orig"]["modules"]["module_dynamic"]["major"]
      assert major
      assert "none" in major
      error_text = major["none"]["tips"]
    else:
      original = Activity.parse(item["orig"])
      error_text = ""
    return ContentForward(
      desc["text"],
      parse_richtext(desc["rich_text_nodes"]),
      original,
      error_text,
    )


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


class ExtraParser(Protocol[TExtra]):
  @staticmethod
  def parse(item: ApiAdditional) -> TExtra:
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
    assert "vote" in item
    return ExtraVote(
      item["vote"]["vote_id"],
      item["vote"]["uid"],
      item["vote"]["desc"],
      item["vote"]["join_num"] or 0,  # 0 人时是 null
      item["vote"]["end_time"],
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
    assert "ugc" in item
    return ExtraVideo(
      int(item["ugc"]["id_str"]),
      item["ugc"]["title"],
      item["ugc"]["desc_second"],
      item["ugc"]["duration"],
      item["ugc"]["cover"],
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
    assert "reserve" in item
    reserve_type = "video" if item["reserve"]["stype"] == 1 else "live"
    if reserve_type == "live":
      if item["reserve"]["button"]["type"] == 1:
        status = "streaming"
      else:
        status = "expired" if "disable" in item["reserve"]["button"]["uncheck"] else "reserving"
    else:
      status = "expired" if item["reserve"]["button"]["type"] == 1 else "reserving"
    desc3 = item["reserve"].get("desc3", None)
    return ExtraReserve(
      item["reserve"]["rid"],
      item["reserve"]["up_mid"],
      item["reserve"]["title"],
      item["reserve"]["desc1"]["text"],
      item["reserve"]["desc2"]["text"],
      item["reserve"]["reserve_total"],
      desc3["text"] if desc3 else "",
      desc3["jump_url"] if desc3 else "",
      reserve_type,
      status,
      item["reserve"]["jump_url"],
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
    assert "goods" in item
    goods = [
      Goods(i["id"], i["name"], i["brief"], i["price"], i["jump_url"], i["cover"])
      for i in item["goods"]["items"]
    ]
    return ExtraGoods(item["goods"]["head_text"], goods)


class ExtraUnknown(ExtraParser["ExtraUnknown"]):
  @staticmethod
  def parse(item: ApiAdditional) -> "ExtraUnknown":
    return ExtraUnknown()


EXTRA_TYPES: dict[str, type[ExtraParser[object]]] = {
  "VOTE": ExtraVote,
  "UGC": ExtraVideo,
  "RESERVE": ExtraReserve,
  "GOODS": ExtraGoods,
}


@dataclass
class Stat:
  repost: int
  like: int
  reply: int


@dataclass
class Extra(Generic[TExtra]):
  type: str
  value: TExtra


@dataclass
class Topic:
  id: int
  name: str


@dataclass
class Activity(Generic[TContent, TExtra]):
  uid: int
  name: str
  avatar: str
  id: int
  top: bool
  type: str
  content: TContent
  stat: Optional[Stat]
  time: int
  extra: Optional[Extra[TExtra]]
  topic: Optional[Topic]

  @staticmethod
  def parse(item: ApiDynamic) -> "Activity[object, object]":
    modules = item["modules"]
    author_module = modules["module_author"]
    top = "module_tag" in modules and modules["module_tag"]["text"] == "置顶"
    stat = None
    if "module_stat" in modules:
      stat_module = modules["module_stat"]
      stat = Stat(
        stat_module["forward"]["count"],
        stat_module["like"]["count"],
        stat_module["comment"]["count"],
      )
    content_type = item["type"].removeprefix("DYNAMIC_TYPE_")
    content_cls = CONTENT_TYPES.get(content_type, ContentUnknown)
    dynamic_module = modules["module_dynamic"]
    extra = None
    if (additional := dynamic_module["additional"]) is not None:
      extra_type = additional["type"].removeprefix("ADDITIONAL_TYPE_")
      extra_cls = EXTRA_TYPES.get(extra_type, ExtraUnknown)
      extra = Extra(extra_type, extra_cls.parse(additional))
    topic = None
    if (raw_topic := dynamic_module["topic"]) is not None:
      topic = Topic(raw_topic["id"], raw_topic["name"])
    return Activity(
      author_module["mid"],
      author_module["name"],
      author_module["face"],
      int(item["id_str"] or 0),
      top,
      content_type,
      content_cls.parse(item),
      stat,
      author_module["pub_ts"],
      extra,
      topic,
    )


ActivityText = Activity[ContentText, TExtra]
ActivityImage = Activity[ContentImage, TExtra]
ActivityArticle = Activity[ContentArticle, TExtra]
ActivityVideo = Activity[ContentVideo, TExtra]
ActivityAudio = Activity[ContentAudio, TExtra]
ActivityPGC = Activity[ContentPGC, TExtra]
ActivityCommon = Activity[ContentCommon, TExtra]
ActivityForward = Activity[ContentForward, TExtra]
ActivityLive = Activity[ContentLive, TExtra]
ActivityLiveRcmd = Activity[ContentLiveRcmd, TExtra]
ActivityCourse = Activity[ContentCourse, TExtra]
ActivityPlaylist = Activity[ContentPlaylist, TExtra]
