"""Все тексты сообщений бота (RU). Удобно править в одном месте."""
from __future__ import annotations

from datetime import datetime

from app.db.models import Opportunity

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


def opportunity_card(opp: Opportunity) -> str:
    lines = [f"<b>{opp.title}</b>", ""]
    if opp.short_description:
        lines.append(opp.short_description)
        lines.append("")
    lines.append(f"⏳ Дедлайн: <b>{fmt_deadline(opp.deadline)}</b>")
    return "\n".join(lines)


def reminder_set(opp: Opportunity, remind_at: datetime) -> str:
    return (
        f"🔔 Готово! Напомню про «{opp.title}» "
        f"{remind_at:%d.%m.%Y} (за неделю до дедлайна)."
    )


def reminder_no_deadline() -> str:
    return "У этой возможности пока нет дедлайна — напоминание поставить не получится."


def reminder_fire(opp: Opportunity) -> str:
    return (
        f"🔔 Напоминание!\n\n«{opp.title}» — дедлайн "
        f"{fmt_deadline(opp.deadline)}.\nУспей подать заявку 🙌"
    )
