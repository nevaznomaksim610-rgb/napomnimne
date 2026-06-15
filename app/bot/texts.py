"""Все тексты сообщений бота (RU). Удобно править в одном месте."""
from __future__ import annotations

from datetime import datetime

from app.db.models import Opportunity
from app.timeutil import to_local

START = (
    "👋 Привет! Я помогу не пропустить дедлайны акселераторов, грантов и "
    "амбассадорств.\n\nВыбери, что тебя интересует:"
)

CHOOSE_CATEGORY = "Выбери категорию:"

EMPTY_CATEGORY = "Пока тут пусто. Загляни позже — мы постоянно обновляем список."

BACK = "⬅️ Назад"


def fmt_deadline(deadline: datetime | None) -> str:
    if deadline is None:
        return "Не скоро"
    return f"до {deadline:%d.%m.%Y}"


def fmt_when(remind_at: datetime) -> str:
    """Момент напоминания (UTC в БД) → локальное «ДД.ММ.ГГГГ в ЧЧ:ММ»."""
    local = to_local(remind_at)
    return f"{local:%d.%m.%Y} в {local:%H:%M}"


def opportunity_card(opp: Opportunity) -> str:
    lines = [f"<b>{opp.title}</b>", ""]
    if opp.short_description:
        lines.append(opp.short_description)
        lines.append("")
    lines.append(f"⏳ Дедлайн: <b>{fmt_deadline(opp.deadline)}</b>")
    return "\n".join(lines)


def reminder_prompt(opp: Opportunity) -> str:
    lines = [f"🔔 Когда напомнить про «{opp.title}»?"]
    if opp.deadline is not None:
        lines.append(f"\nДедлайн: {fmt_deadline(opp.deadline)}.")
    lines.append("\nВыбери вариант ниже:")
    return "\n".join(lines)


def reminder_set(opp: Opportunity, remind_at: datetime) -> str:
    return (
        f"🔔 Готово! Напомню про «{opp.title}»\n"
        f"📅 {fmt_when(remind_at)} (МСК)."
    )


ASK_DATE = (
    "📅 Напиши дату, когда напомнить.\n\n"
    "Формат: <b>ДД.ММ.ГГГГ</b> или с временем <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>\n"
    "Например: <code>30.09.2026</code> или <code>30.09.2026 18:00</code>\n\n"
    "Если время не указать — напомню в 09:00."
)

DATE_BAD = (
    "🤔 Не понял дату. Нужен формат <b>ДД.ММ.ГГГГ</b> "
    "или <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>.\nПопробуй ещё раз."
)

DATE_PAST = "⏳ Эта дата уже прошла. Укажи будущую дату."

MY_REMINDERS_TITLE = "🔔 Твои напоминания\n\nНажми на напоминание, чтобы отменить его."

MY_REMINDERS_EMPTY = (
    "🔕 У тебя пока нет напоминаний.\n\n"
    "Открой любую программу и нажми «🔔 Напоминание»."
)

REMINDER_CANCELLED = "✅ Напоминание отменено."


def reminder_fire(opp: Opportunity) -> str:
    lines = ["🔔 <b>Напоминание!</b>", "", f"«{opp.title}»"]
    if opp.deadline is not None:
        lines.append(f"⏳ Дедлайн: {fmt_deadline(opp.deadline)}")
    lines.append("\nНе забудь подать заявку 🙌")
    return "\n".join(lines)
