"""Модели SQLAlchemy."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import Category, MessageDirection, OutreachStage, ThreadStatus


class Base(DeclarativeBase):
    pass


class Opportunity(Base):
    """Возможность/мероприятие — ядро системы."""

    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[Category] = mapped_column(Enum(Category), index=True)
    title: Mapped[str] = mapped_column(String(255))
    short_description: Mapped[str] = mapped_column(Text, default="")
    application_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Данные для аутрича
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    stage: Mapped[OutreachStage] = mapped_column(
        Enum(OutreachStage), default=OutreachStage.NEW, index=True
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    reminders: Mapped[list["Reminder"]] = relationship(back_populates="opportunity")
    thread: Mapped["EmailThread | None"] = relationship(
        back_populates="opportunity", uselist=False
    )


class User(Base):
    """Пользователь Telegram."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram_id
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reminders: Mapped[list["Reminder"]] = relationship(back_populates="user")


class Reminder(Base):
    """Подписка пользователя на напоминание о дедлайне."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), index=True
    )
    remind_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    offset_days: Mapped[int] = mapped_column(Integer, default=7)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="reminders")
    opportunity: Mapped["Opportunity"] = relationship(back_populates="reminders")


class EmailThread(Base):
    """Переписка по конкретной возможности."""

    __tablename__ = "email_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), unique=True, index=True
    )
    subject: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[ThreadStatus] = mapped_column(
        Enum(ThreadStatus), default=ThreadStatus.OPEN, index=True
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    followups_sent: Mapped[int] = mapped_column(Integer, default=0)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="thread")
    messages: Mapped[list["EmailMessage"]] = relationship(back_populates="thread")


class EmailMessage(Base):
    """Отдельное письмо (входящее или исходящее)."""

    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id"), index=True)
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection))
    subject: Mapped[str] = mapped_column(String(512), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Результат разбора DeepSeek (JSON-строка), только для входящих
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_analyzed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    thread: Mapped["EmailThread"] = relationship(back_populates="messages")
