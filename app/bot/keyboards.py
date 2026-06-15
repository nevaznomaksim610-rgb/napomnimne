"""Инлайн-клавиатуры. Callback-формат: 'cat:<category>', 'opp:<id>',
'remind:<id>', 'home'."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.texts import BACK, fmt_deadline
from app.db.enums import Category
from app.db.models import Opportunity


def categories_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in Category:
        kb.button(text=cat.title, callback_data=f"cat:{cat.value}")
    kb.adjust(1)
    return kb.as_markup()


def catalog_kb(category: Category, items: list[Opportunity]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for opp in items:
        label = f"{opp.title} — ⏳ {fmt_deadline(opp.deadline)}"
        kb.button(text=label, callback_data=f"opp:{opp.id}")
    kb.button(text=BACK, callback_data="home")
    kb.adjust(1)
    return kb.as_markup()


def opportunity_kb(opp: Opportunity) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if opp.application_url:
        kb.row(InlineKeyboardButton(text="📝 Подать заявку", url=opp.application_url))
    if opp.deadline is not None:
        kb.row(
            InlineKeyboardButton(
                text="🔔 Поставить напоминание", callback_data=f"remind:{opp.id}"
            )
        )
    kb.row(
        InlineKeyboardButton(text=BACK, callback_data=f"cat:{opp.category.value}")
    )
    return kb.as_markup()
