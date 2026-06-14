"""Заполнение каталога возможностей из catalog_data.CATALOG.

Идемпотентно: если в таблице opportunities уже есть записи — ничего не делает.
Все программы публикуются сразу (is_published=True), но в стадии CONFIRMED —
агент их НЕ трогает рассылкой, пока заказчик не утвердит тексты писем и не
переведёт нужные программы в стадию NEW.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .catalog_data import CATALOG
from .enums import Category, OutreachStage
from .models import Opportunity


async def seed_catalog_if_empty(session: AsyncSession) -> int:
    """Залить каталог, если он пуст. Возвращает число добавленных записей."""
    count = await session.scalar(select(func.count()).select_from(Opportunity))
    if count:
        return 0

    for cat, title, organizer, description, email in CATALOG:
        session.add(
            Opportunity(
                category=Category[cat],
                title=title,
                contact_name=organizer or None,
                short_description=description,
                contact_email=email,
                deadline=None,
                application_url=None,
                stage=OutreachStage.CONFIRMED,  # видимы в боте, но агент не пишет
                is_published=True,
            )
        )
    await session.commit()
    return len(CATALOG)
