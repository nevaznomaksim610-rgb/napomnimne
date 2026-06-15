"""Сборка бота: Bot, Dispatcher, регистрация роутеров."""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings

from .handlers import catalog, reminders, start


def build_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher() -> Dispatcher:
    # MemoryStorage хватает: FSM используется только для разового ввода даты,
    # терять это состояние при рестарте не страшно (один реплика на Railway).
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(reminders.router)
    return dp
