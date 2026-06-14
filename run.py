"""Точка входа: инициализация БД, запуск планировщика и polling бота."""
from __future__ import annotations

import asyncio
import logging

from app.bot.main import build_bot, build_dispatcher
from app.db.base import init_db
from app.scheduler.jobs import build_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)


async def main() -> None:
    await init_db()

    bot = build_bot()
    dp = build_dispatcher()

    scheduler = build_scheduler(bot)
    scheduler.start()

    logging.getLogger("run").info("Бот запущен. Планировщик активен.")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
