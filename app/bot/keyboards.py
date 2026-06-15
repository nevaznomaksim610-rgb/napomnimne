"""Инлайн-клавиатуры. Callback-формат:
'cat:<category>', 'opp:<id>', 'home', 'myrem',
'remopts:<id>'           — открыть меню «когда напомнить»,
'rem:<id>:<kind>'        — поставить напоминание (kind: n1/n3/n7, d7/d3/d1/d0, date),
'remcancel:<id>'         — отменить напоминание.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.texts import BACK, fmt_deadline, fmt_when
from app.db.enums import Category
from app.db.models import Opportunity, Reminder
from app.timeutil import deadline_remind_utc, now_utc

MY_REMINDERS_BTN = "🔔 Мои напоминания"

# Быстрые интервалы «через N дней» (kind = n<N>) — доступны всегда.
_RELATIVE_OPTIONS: list[tuple[int, str]] = [
    (1, "Через день"),
    (3, "Через 3 дня"),
    (7, "Через неделю"),
]

# Сдвиги «за N дней до дедлайна» (kind = d<N>) — только если дедлайн есть
# и момент ещё не прошёл.
_DEADLINE_OPTIONS: list[tuple[int, str]] = [
    (7, "За неделю до дедлайна"),
    (3, "За 3 дня до дедлайна"),
    (1, "За день до дедлайна"),
    (0, "В день дедлайна"),
]


def categories_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in Category:
        kb.button(text=cat.title, callback_data=f"cat:{cat.value}")
    kb.button(text=MY_REMINDERS_BTN, callback_data="myrem")
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
    kb.row(
        InlineKeyboardButton(
            text="🔔 Напоминание", callback_data=f"remopts:{opp.id}"
        )
    )
    kb.row(
        InlineKeyboardButton(text=BACK, callback_data=f"cat:{opp.category.value}")
    )
    return kb.as_markup()


def reminder_options_kb(opp: Opportunity) -> InlineKeyboardMarkup:
    """Меню «когда напомнить» для конкретной возможности."""
    kb = InlineKeyboardBuilder()

    if opp.deadline is not None:
        now = now_utc()
        for offset, label in _DEADLINE_OPTIONS:
            if deadline_remind_utc(opp.deadline, offset) > now:
                kb.button(text=f"⏰ {label}", callback_data=f"rem:{opp.id}:d{offset}")

    for days, label in _RELATIVE_OPTIONS:
        kb.button(text=f"⏰ {label}", callback_data=f"rem:{opp.id}:n{days}")

    kb.button(text="📅 Выбрать дату", callback_data=f"rem:{opp.id}:date")
    kb.button(text=BACK, callback_data=f"opp:{opp.id}")
    kb.adjust(1)
    return kb.as_markup()


def reminder_done_kb() -> InlineKeyboardMarkup:
    """Кнопки после успешной постановки напоминания."""
    kb = InlineKeyboardBuilder()
    kb.button(text=MY_REMINDERS_BTN, callback_data="myrem")
    kb.button(text="⬅️ В меню", callback_data="home")
    kb.adjust(1)
    return kb.as_markup()


def my_reminders_kb(reminders: list[Reminder]) -> InlineKeyboardMarkup:
    """Список напоминаний пользователя; тап по строке — отмена."""
    kb = InlineKeyboardBuilder()
    for r in reminders:
        title = r.opportunity.title if r.opportunity else "—"
        kb.button(
            text=f"❌ {fmt_when(r.remind_at)} · {title}",
            callback_data=f"remcancel:{r.id}",
        )
    kb.button(text="⬅️ В меню", callback_data="home")
    kb.adjust(1)
    return kb.as_markup()


def reminder_fire_kb(opp: Opportunity) -> InlineKeyboardMarkup | None:
    """Кнопка «подать заявку» в самом напоминании, если есть ссылка."""
    if not opp.application_url:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Подать заявку", url=opp.application_url)
    return kb.as_markup()
