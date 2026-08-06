import random
import time
from datetime import datetime, timedelta
from typing import Literal, cast

from arclet.alconna import (
    Alconna,
    AllParam,
    Args,
    CommandMeta,
    Option,
    store_true,
)
from arclet.entari import MessageChain, Session, command, metadata, plugin_config
from arclet.entari.config import EntariConfig
from arclet.letoderea import propagate
from entari_plugin_database import AsyncSession, Base
from entari_plugin_permission import require_permission
from pydantic import BaseModel, HttpUrl, SecretStr, TypeAdapter
from sqlalchemy import desc, select
from sqlalchemy.orm import Mapped, mapped_column
from typing_extensions import TypedDict

from idhagnbot.http import get_session
from idhagnbot.plugins.fallback import register_exception_explain


class Config(BaseModel):
    key: SecretStr = SecretStr("")
    server: HttpUrl = HttpUrl("https://api.openai.com/v1")
    model: str = "gpt-4.1"
    system: str = ""
    info: Literal["user", "system", False] = "user"
    secret: bool = False
    history_time: timedelta = timedelta(1)
    history_limit: int = 100
    timer: bool | float = False

    def should_send_timer(self, duration: float) -> bool:
        if isinstance(self.timer, bool):
            return self.timer
        return duration > self.timer


metadata("", config=Config)
CONFIG = plugin_config(Config)


def extract_nickname(session: Session) -> str:
    if session.event.member and session.event.member.nick:
        return session.event.member.nick
    return session.user.nick or session.user.name or session.user.id


def is_superuser(session: Session) -> bool:
    superusers = EntariConfig.instance.basic.superusers.get(session.account.platform)
    if superusers:
        return session.user.id in superusers
    return False


class History(Base):
    __tablename__ = "idhagnbot_openai_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str]
    channel_id: Mapped[str]
    role: Mapped[Literal["user", "assistant"]]
    nickname: Mapped[str]
    superuser: Mapped[bool]
    content: Mapped[str]
    time: Mapped[datetime]
    ignored: Mapped[bool]


class Ignore(Base):
    __tablename__ = "idhagnbot_openai_ignore"
    platform: Mapped[str] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(primary_key=True)
    time: Mapped[datetime]


class ResMessage(TypedDict):
    content: str


class ResChoice(TypedDict):
    message: ResMessage


class ResDataSuccess(TypedDict):
    created: int
    choices: list[ResChoice]


class ResError(TypedDict):
    code: int
    message: str


class ResDataError(TypedDict):
    error: ResError


type ResData = ResDataSuccess | ResDataError
ResDataAdapter: TypeAdapter[ResData] = TypeAdapter(ResData)


class ReqMessage(TypedDict):
    role: Literal["user", "system", "assistant"]
    content: str


class ReqData(TypedDict):
    model: str
    messages: list[ReqMessage]


class OpenAIException(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(code, message)
        self.code: int = code
        self.message: str = message


@register_exception_explain
def ai_exception_explain(exception: BaseException) -> str | None:
    if isinstance(exception, OpenAIException):
        return (
            "AI 供应商异常\n"
            "可能是输入或输出中包含敏感内容，额度用完了，亦或是供应商真的炸了。"
        )
    return None


@command.on(
    Alconna(
        "ai",
        Option(
            "--no-context",
            dest="no_context",
            action=store_true,
            default=False,
            help_text="禁用上下文",
        ),
        Args["message", AllParam(str)],
        meta=CommandMeta("AI对话"),
    ),
)
@propagate(require_permission("idhagnbot.openai.ai", prompt=True))
async def handle_ai(
    session: Session,
    db: AsyncSession,
    no_context: bool,
    message: MessageChain,
) -> str:
    now = datetime.now()
    if no_context:
        history: list[History] = []
    else:
        ignore_time = await db.get(
            Ignore,
            (session.account.platform, session.channel.id),
        )
        min_time = now - CONFIG.history_time
        min_time = max(min_time, ignore_time.time) if ignore_time else min_time
        history = list(
            await db.scalars(
                select(History)
                .where(
                    History.platform == session.account.platform,
                    History.channel_id == session.channel.id,
                    History.time > min_time,
                    ~History.ignored,
                )
                .order_by(desc(History.time))
                .limit(CONFIG.history_limit),
            ),
        )
    current = History(
        platform=session.account.platform,
        channel_id=session.channel.id,
        role="user",
        nickname=extract_nickname(session),
        superuser=is_superuser(session),
        content=message.extract_plain_text(),
        time=now,
        ignored=no_context,
    )
    history.append(current)
    secret = random.randint(1000, 9999) if CONFIG.secret else 0
    messages: list[ReqMessage] = []
    if CONFIG.system:
        messages.append(
            ReqMessage(role="system", content=CONFIG.system.format(secret=secret)),
        )
    for item in history:
        content = item.content
        if item.role == "user":
            if CONFIG.info == "system":
                secret_info = (
                    f"，带有暗号{secret}" if CONFIG.secret and item.superuser else ""
                )
                messages.append(
                    ReqMessage(
                        role="system",
                        content=f"下一条消息来自{item.nickname}{secret_info}，"
                        f"发送于{item.time:%Y-%m-%d %H:%M:%S}",
                    ),
                )
            elif CONFIG.info == "user":
                secret_info = (
                    f"带暗号{secret}" if CONFIG.secret and item.superuser else ""
                )
                content = (
                    f"{item.nickname}在{item.time:%Y-%m-%d %H:%M:%S}{secret_info}说："
                    + content
                )
        messages.append(ReqMessage(role=item.role, content=content))
    time_start = time.perf_counter()
    async with get_session().post(
        f"{CONFIG.server}/chat/completions",
        headers={"Authorization": f"Bearer {CONFIG.key.get_secret_value()}"},
        json=ReqData(model=CONFIG.model, messages=messages),
    ) as response:
        data = ResDataAdapter.validate_python(await response.json())
    time_end = time.perf_counter()
    timer = time_end - time_start
    if "error" in data:
        # 没法用 closed=True 因为 Pydantic 的 extra="ignore" 无效
        error = cast("ResError", data["error"])
        raise OpenAIException(error["code"], error["message"])
    content = data["choices"][0]["message"]["content"]
    db.add(current)
    db.add(
        History(
            platform=session.account.platform,
            channel_id=session.channel.id,
            role="assistant",
            nickname="",
            superuser=False,
            content=content,
            time=datetime.fromtimestamp(data["created"]),
            ignored=no_context,
        ),
    )
    await db.commit()
    if CONFIG.should_send_timer(timer):
        content += f"\n({timer:.1f}s)"
    return content


@command.on(Alconna("ai重置", meta=CommandMeta("重置AI对话上下文")))
@propagate(require_permission("idhagnbot.openai.reset", prompt=True))
async def handle_reset(session: Session, db: AsyncSession) -> str:
    await db.merge(
        Ignore(
            platform=session.account.platform,
            channel_id=session.channel.id,
            time=datetime.now(),
        ),
    )
    await db.commit()
    return "已重置上下文"
