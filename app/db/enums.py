"""Перечисления, используемые в моделях."""
from __future__ import annotations

import enum


class Category(str, enum.Enum):
    """Категории возможностей (верхнее меню бота)."""

    ACCELERATOR = "accelerator"
    GRANT = "grant"
    AMBASSADOR = "ambassador"

    @property
    def title(self) -> str:
        return {
            Category.ACCELERATOR: "🚀 Акселераторы",
            Category.GRANT: "💰 Гранты",
            Category.AMBASSADOR: "🤝 Амбассадорства",
        }[self]


class OutreachStage(str, enum.Enum):
    """Этап готовности возможности (конечный автомат агента)."""

    NEW = "new"                  # ещё не писали
    CONTACTED = "contacted"      # отправлено первое письмо
    FOLLOW_UP_1 = "follow_up_1"  # отправлен 1-й follow-up
    FOLLOW_UP_2 = "follow_up_2"  # отправлен 2-й follow-up
    REPLIED = "replied"          # пришёл ответ, ещё не разобран
    NEEDS_INFO = "needs_info"    # ответ есть, но нужна доп. информация
    CONFIRMED = "confirmed"      # условия/дедлайн подтверждены → публикуем
    REJECTED = "rejected"        # отказ
    STALLED = "stalled"          # нет ответа после всех follow-up


# Этапы, при которых возможность показывается пользователям в боте
PUBLISHABLE_STAGES = {OutreachStage.CONFIRMED}


class MessageDirection(str, enum.Enum):
    OUT = "out"  # мы написали
    IN = "in"    # нам ответили


class ThreadStatus(str, enum.Enum):
    OPEN = "open"
    WAITING = "waiting"     # ждём ответа
    ANSWERED = "answered"   # ответ получен
    CLOSED = "closed"
