"""Логика последовательности рассылок.

Шаблоны писем — заглушки: финальные тексты пришлёт заказчик (раздел 7
ARCHITECTURE.md). Каждая функция работает в рамках переданной сессии и
не коммитит — это делает вызывающий job.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.email_client import send_email
from app.db.enums import OutreachStage, ThreadStatus
from app.db.models import EmailMessage, EmailThread, Opportunity
from app.db.enums import MessageDirection
from config import settings

# ── Шаблоны писем (TODO: заменить на реальные тексты заказчика) ──
SIGNATURE = "\n\n—\nС уважением, команда проекта"


def _initial_template(opp: Opportunity) -> tuple[str, str]:
    subject = f"Сотрудничество: {opp.title}"
    body = (
        f"Здравствуйте{', ' + opp.contact_name if opp.contact_name else ''}!\n\n"
        "Пишем по поводу участия/подачи заявки. Подскажите, пожалуйста, "
        "актуальные сроки и условия участия.\n\n"
        "Будем благодарны за информацию." + SIGNATURE
    )
    return subject, body


def _followup_template(opp: Opportunity, n: int) -> tuple[str, str]:
    subject = f"Re: Сотрудничество: {opp.title}"
    body = (
        "Здравствуйте!\n\n"
        "Поднимаю предыдущее письмо — возможно, оно затерялось. "
        "Подскажите, пожалуйста, актуальные сроки и условия." + SIGNATURE
    )
    return subject, body


async def send_initial(session: AsyncSession, opp: Opportunity) -> str:
    """Первое письмо по возможности. Создаёт тред."""
    subject, body = _initial_template(opp)
    message_id = await send_email(opp.contact_email, subject, body)
    now = datetime.utcnow()

    thread = EmailThread(
        opportunity_id=opp.id,
        subject=subject,
        status=ThreadStatus.WAITING,
        last_sent_at=now,
        next_action_at=now + timedelta(days=settings.followup_delay_days),
        followups_sent=0,
    )
    session.add(thread)
    await session.flush()

    session.add(
        EmailMessage(
            thread_id=thread.id,
            direction=MessageDirection.OUT,
            subject=subject,
            body=body,
            message_id=message_id,
        )
    )
    opp.stage = OutreachStage.CONTACTED
    return f"✉️ Отправлено первое письмо: «{opp.title}» → {opp.contact_email}"


async def send_followup(session: AsyncSession, thread: EmailThread) -> str:
    """Follow-up по треду, где не дождались ответа."""
    opp = thread.opportunity
    n = thread.followups_sent + 1
    subject, body = _followup_template(opp, n)
    message_id = await send_email(opp.contact_email, subject, body)
    now = datetime.utcnow()

    thread.last_sent_at = now
    thread.followups_sent = n
    thread.next_action_at = now + timedelta(days=settings.followup_delay_days)

    session.add(
        EmailMessage(
            thread_id=thread.id,
            direction=MessageDirection.OUT,
            subject=subject,
            body=body,
            message_id=message_id,
        )
    )
    opp.stage = (
        OutreachStage.FOLLOW_UP_1 if n == 1 else OutreachStage.FOLLOW_UP_2
    )
    if n >= settings.max_followups:
        thread.next_action_at = None  # больше не дёргаем
        opp.stage = OutreachStage.STALLED
    return f"🔁 Follow-up #{n}: «{opp.title}»"
