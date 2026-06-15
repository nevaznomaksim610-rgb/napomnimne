"""Работа со временем: в БД всё хранится как наивный UTC (datetime.utcnow()),
а пользователю показываем/считаем в его часовом поясе (settings.timezone).

Здесь собраны конверсии между наивным UTC и наивным локальным временем,
чтобы остальной код не путался с tzinfo.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import settings


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def now_utc() -> datetime:
    """Текущее время как наивный UTC — единый формат хранения в БД."""
    return datetime.utcnow()


def to_utc(local_naive: datetime) -> datetime:
    """Наивное локальное время → наивный UTC."""
    return (
        local_naive.replace(tzinfo=_tz())
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def to_local(utc_naive: datetime) -> datetime:
    """Наивный UTC → наивное локальное время."""
    return (
        utc_naive.replace(tzinfo=timezone.utc)
        .astimezone(_tz())
        .replace(tzinfo=None)
    )


def deadline_remind_utc(deadline: datetime, offset_days: int) -> datetime:
    """Когда напомнить «за offset_days до дедлайна»: в settings.reminder_hour
    по локальному времени, за offset_days до даты дедлайна. Возвращает UTC."""
    local = datetime(
        deadline.year, deadline.month, deadline.day, settings.reminder_hour, 0
    ) - timedelta(days=offset_days)
    return to_utc(local)
