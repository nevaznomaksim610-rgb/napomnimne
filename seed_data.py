"""Локальное наполнение БД реальным каталогом из catalog_data.CATALOG.

Запуск:  python seed_data.py
Идемпотентно: если каталог уже заполнен — ничего не делает.
"""
from __future__ import annotations

import asyncio

from app.db.base import async_session, init_db
from app.db.seeder import seed_catalog_if_empty


async def main() -> None:
    await init_db()
    async with async_session() as session:
        added = await seed_catalog_if_empty(session)
    if added:
        print(f"Добавлено {added} программ.")
    else:
        print("Каталог уже заполнен — пропускаю.")


if __name__ == "__main__":
    asyncio.run(main())
