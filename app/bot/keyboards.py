"""Инлайн-клавиатуры. Callback-формат: 'cat:<category>', 'opp:<id>',
'remind:<id>', 'home'."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.texts import BACK, fmt_deadline
from app.db.enums import Category
from app.db.models import Opportunity

# Telegram всегда центрирует текст на инлайн-кнопках; настройки «по левому краю»
# в Bot API нет. Чтобы левые края подписей всё же встали в одну линию, добиваем
# короткие подписи неразрывными пробелами до ширины самой длинной — тогда при
# центрировании короткие занимают всю ширину и текст начинается слева.
NBSP = " "


def _left_align(labels: list[str]) -> list[str]:
    width = max(len(label) for label in labels)
    return [label + NBSP * (width - len(label)) for label in labels]


def categories_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    titles = _left_align([cat.title for cat in Category])
    for cat, title in zip(Category, titles):
        kb.button(text=title, callback_data=f"cat:{cat.value}")
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
