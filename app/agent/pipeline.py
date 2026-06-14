"""Конечный автомат «этапов готовности».

Принимает результат анализа DeepSeek и применяет переход к Opportunity:
меняет stage, при необходимости проставляет deadline/описание и публикует.
"""
from __future__ import annotations

from datetime import datetime

from app.agent.analyzer import Analysis
from app.db.enums import OutreachStage, ThreadStatus
from app.db.models import EmailThread, Opportunity


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def apply_analysis(
    opp: Opportunity, analysis: Analysis, thread: EmailThread | None = None
) -> str:
    """Меняет состояние opp/thread на основе разбора. Возвращает текст уведомления."""
    # 1) Отказ — закрываем и снимаем с публикации.
    if analysis.intent == "negative":
        opp.stage = OutreachStage.REJECTED
        opp.is_published = False
        if thread is not None:
            thread.status = ThreadStatus.CLOSED
            thread.next_action_at = None
        return f"❌ «{opp.title}»: отказ. {analysis.summary}"

    # 2) Названа ТОЧНАЯ дата — обновляем дедлайн в БД и публикуем.
    exact = _parse(analysis.deadline)
    if exact is not None:
        opp.deadline = exact
        opp.stage = OutreachStage.CONFIRMED
        opp.is_published = True
        if analysis.summary and not opp.short_description:
            opp.short_description = analysis.summary
        if thread is not None:
            thread.status = ThreadStatus.ANSWERED
            thread.next_action_at = None
        return (
            f"✅ «{opp.title}»: дата подтверждена — {exact:%d.%m.%Y}, "
            f"обновлено в БД. {analysis.summary}"
        )

    # 3) Точной даты нет, но просят написать позже — «не скоро».
    recontact = _parse(analysis.recontact_date)
    if recontact is not None:
        opp.stage = OutreachStage.DEFERRED
        if thread is not None:
            thread.status = ThreadStatus.WAITING
            thread.next_action_at = recontact  # агент напишет в эту дату
        return (
            f"🕓 «{opp.title}»: пока без точной даты — напишем снова "
            f"{recontact:%d.%m.%Y}. {analysis.summary}"
        )

    # 4) Просят прислать информацию.
    if analysis.intent == "needs_info":
        opp.stage = OutreachStage.NEEDS_INFO
        req = analysis.requirements or "нужна доп. информация"
        if thread is not None:
            thread.next_action_at = None
        return f"📨 «{opp.title}»: запросили информацию — {req}"

    # 5) neutral / непонятно — ответ есть, нужен ручной взгляд.
    opp.stage = OutreachStage.REPLIED
    if thread is not None:
        thread.next_action_at = None
    return f"📩 «{opp.title}»: пришёл ответ, требуется внимание. {analysis.summary}"
