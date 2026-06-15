"""CRUD-функции поверх моделей. Каждая принимает открытую сессию."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings

from .enums import Category, OutreachStage
from .models import EmailThread, Opportunity, Reminder, User


# ── Пользователи ────────────────────────────────────────────
async def upsert_user(
    session: AsyncSession, telegram_id: int, username: str | None, first_name: str | None
) -> User:
    user = await session.get(User, telegram_id)
    if user is None:
        user = User(id=telegram_id, username=username, first_name=first_name)
        session.add(user)
    else:
        user.username = username
        user.first_name = first_name
    await session.flush()
    return user


# ── Каталог (бот) ───────────────────────────────────────────
async def list_published(
    session: AsyncSession, category: Category
) -> list[Opportunity]:
    """Опубликованные возможности категории — для каталога бота."""
    stmt = (
        select(Opportunity)
        .where(
            Opportunity.category == category,
            Opportunity.is_published.is_(True),
        )
        .order_by(Opportunity.deadline.is_(None), Opportunity.deadline.asc())
    )
    return list((await session.scalars(stmt)).all())


async def get_opportunity(
    session: AsyncSession, opportunity_id: int
) -> Opportunity | None:
    return await session.get(Opportunity, opportunity_id)


# ── Напоминания ─────────────────────────────────────────────
# offset_days = -1 — пометка «время задано вручную» (интервал/точная дата),
# а не «за N дней до дедлайна».
CUSTOM_OFFSET = -1


async def add_reminder(
    session: AsyncSession,
    user_id: int,
    opportunity_id: int,
    remind_at: datetime,
    offset_days: int = CUSTOM_OFFSET,
) -> Reminder:
    """Создать напоминание на конкретный момент (UTC). Дубли (тот же
    пользователь+возможность+время, ещё не отправленные) не плодим."""
    existing = await session.scalar(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.opportunity_id == opportunity_id,
            Reminder.remind_at == remind_at,
            Reminder.is_sent.is_(False),
        )
    )
    if existing:
        return existing

    reminder = Reminder(
        user_id=user_id,
        opportunity_id=opportunity_id,
        remind_at=remind_at,
        offset_days=offset_days,
    )
    session.add(reminder)
    await session.flush()
    return reminder


async def list_user_reminders(
    session: AsyncSession, user_id: int
) -> list[Reminder]:
    """Активные (ещё не отправленные) напоминания пользователя с возможностями."""
    stmt = (
        select(Reminder)
        .where(Reminder.user_id == user_id, Reminder.is_sent.is_(False))
        .order_by(Reminder.remind_at.asc())
        .options(selectinload(Reminder.opportunity))
    )
    return list((await session.scalars(stmt)).all())


async def get_user_reminder(
    session: AsyncSession, reminder_id: int, user_id: int
) -> Reminder | None:
    reminder = await session.get(Reminder, reminder_id)
    if reminder is None or reminder.user_id != user_id:
        return None
    return reminder


async def delete_reminder(
    session: AsyncSession, reminder_id: int, user_id: int
) -> bool:
    """Удалить напоминание, если оно принадлежит пользователю."""
    reminder = await get_user_reminder(session, reminder_id, user_id)
    if reminder is None:
        return False
    await session.delete(reminder)
    return True


async def due_reminders(session: AsyncSession, now: datetime) -> list[Reminder]:
    stmt = select(Reminder).where(
        Reminder.is_sent.is_(False),
        Reminder.remind_at <= now,
    )
    return list((await session.scalars(stmt)).all())


# ── Агент: выборки для рассылки ─────────────────────────────
async def opportunities_to_contact(session: AsyncSession) -> list[Opportunity]:
    """Новые возможности с почтой — кому ещё не писали."""
    stmt = select(Opportunity).where(
        Opportunity.stage == OutreachStage.NEW,
        Opportunity.contact_email.is_not(None),
    )
    return list((await session.scalars(stmt)).all())


async def threads_needing_followup(
    session: AsyncSession, now: datetime
) -> list[EmailThread]:
    """Треды, где пора слать follow-up (ждём первый ответ, лимит не достигнут).

    «Отложенные» (stage=DEFERRED) сюда не попадают — их ведёт отдельная задача.
    """
    chasing = {
        OutreachStage.CONTACTED,
        OutreachStage.FOLLOW_UP_1,
        OutreachStage.FOLLOW_UP_2,
    }
    stmt = (
        select(EmailThread)
        .join(Opportunity, EmailThread.opportunity_id == Opportunity.id)
        .where(
            EmailThread.next_action_at.is_not(None),
            EmailThread.next_action_at <= now,
            EmailThread.followups_sent < settings.max_followups,
            Opportunity.stage.in_(chasing),
        )
    )
    return list((await session.scalars(stmt)).all())


async def threads_deferred_due(
    session: AsyncSession, now: datetime
) -> list[EmailThread]:
    """«Отложенные» треды (stage=DEFERRED), у которых настала дата повторного письма."""
    stmt = (
        select(EmailThread)
        .join(Opportunity, EmailThread.opportunity_id == Opportunity.id)
        .where(
            EmailThread.next_action_at.is_not(None),
            EmailThread.next_action_at <= now,
            Opportunity.stage == OutreachStage.DEFERRED,
        )
    )
    return list((await session.scalars(stmt)).all())
