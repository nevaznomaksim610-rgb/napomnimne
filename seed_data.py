"""Наполнение БД демо-данными, чтобы сразу потыкать бота.

Запуск:  python seed_data.py
Часть возможностей опубликована (видны в боте), часть — в работе у агента.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.db.base import async_session, init_db
from app.db.enums import Category, OutreachStage
from app.db.models import Opportunity

NOW = datetime.utcnow()

DEMO = [
    Opportunity(
        category=Category.ACCELERATOR,
        title="Demo Accelerator Spring",
        short_description=(
            "3-месячная программа для ранних стартапов с грантом $50k и менторами. "
            "Помогают довести продукт до раунда и питча перед инвесторами."
        ),
        application_url="https://example.com/apply",
        deadline=NOW + timedelta(days=20),
        contact_email="hello@demo-accel.example",
        contact_name="Demo Accelerator",
        stage=OutreachStage.CONFIRMED,
        is_published=True,
    ),
    Opportunity(
        category=Category.GRANT,
        title="Open Tech Grant",
        short_description=(
            "Грант до $10k на развитие open-source проектов. "
            "Подходит командам и соло-разработчикам, отчётность минимальная."
        ),
        deadline=NOW + timedelta(days=40),
        contact_email="grants@opentech.example",
        contact_name="Open Tech Foundation",
        stage=OutreachStage.CONFIRMED,
        is_published=True,
    ),
    Opportunity(
        category=Category.AMBASSADOR,
        title="Crypto Ambassador Program",
        short_description=(
            "Амбассадорство с бонусами, мерчем и доступом к закрытому комьюнити. "
            "Задача — вести активности и приводить новых участников."
        ),
        deadline=NOW + timedelta(days=10),
        contact_email="amb@cryptohub.example",
        contact_name="CryptoHub",
        stage=OutreachStage.CONFIRMED,
        is_published=True,
    ),
    # ещё не обработана агентом — в боте не видна
    Opportunity(
        category=Category.ACCELERATOR,
        title="Stealth Accelerator (in progress)",
        short_description="",
        contact_email="info@stealth-accel.example",
        contact_name="Stealth",
        stage=OutreachStage.NEW,
        is_published=False,
    ),
]


async def main() -> None:
    await init_db()
    async with async_session() as session:
        session.add_all(DEMO)
        await session.commit()
    print(f"Добавлено {len(DEMO)} демо-возможностей.")


if __name__ == "__main__":
    asyncio.run(main())
