"""CRUD-функции поверх моделей. Каждая принимает открытую сессию."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
async def create_reminder(
    session: AsyncSession, user_id: int, opp: Opportunity
) -> Reminder | None:
    """Создать напоминание за N дней до дедлайна. None — если дедлайна нет."""
    if opp.deadline is None:
        return None
    remind_at = opp.deadline - timedelta(days=settings.reminder_offset_days)

    # не дублируем
    existing = await session.scalar(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.opportunity_id == opp.id,
            Reminder.is_sent.is_(False),
        )
    )
    if existing:
        return existing

    reminder = Reminder(
        user_id=user_id,
        opportunity_id=opp.id,
        remind_at=remind_at,
        offset_days=settings.reminder_offset_days,
    )
    session.add(reminder)
    await session.flush()
    return reminder


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
    """Треды, где пора слать follow-up (срок истёк, лимит не достигнут)."""
    stmt = select(EmailThread).where(
        EmailThread.next_action_at.is_not(None),
        EmailThread.next_action_at <= now,
        EmailThread.followups_sent < settings.max_followups,
    )
    return list((await session.scalars(stmt)).all())
