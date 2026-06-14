"""Конечный автомат «этапов готовности».

Принимает результат анализа DeepSeek и применяет переход к Opportunity:
меняет stage, при необходимости проставляет deadline/описание и публикует.
"""
from __future__ import annotations

from datetime import datetime

from app.agent.analyzer import Analysis
from app.db.enums import OutreachStage
from app.db.models import Opportunity


def apply_analysis(opp: Opportunity, analysis: Analysis) -> str:
    """Меняет состояние opp на основе разбора. Возвращает текст для лога/уведомления."""
    # подтянуть дедлайн, если агент его выяснил
    if analysis.deadline and opp.deadline is None:
        try:
            opp.deadline = datetime.strptime(analysis.deadline, "%Y-%m-%d")
        except ValueError:
            pass

    if analysis.intent == "negative":
        opp.stage = OutreachStage.REJECTED
        opp.is_published = False
        return f"❌ «{opp.title}»: отказ. {analysis.summary}"

    if analysis.intent == "positive" and analysis.next_action == "publish":
        opp.stage = OutreachStage.CONFIRMED
        opp.is_published = True
        if analysis.summary and not opp.short_description:
            opp.short_description = analysis.summary
        return f"✅ «{opp.title}»: подтверждено и опубликовано. {analysis.summary}"

    if analysis.intent == "needs_info":
        opp.stage = OutreachStage.NEEDS_INFO
        req = analysis.requirements or "нужна доп. информация"
        return f"📨 «{opp.title}»: запросили информацию — {req}"

    # neutral / непонятно — пометим, что ответ есть, разбор ручной
    opp.stage = OutreachStage.REPLIED
    return f"📩 «{opp.title}»: пришёл ответ, требуется внимание. {analysis.summary}"
