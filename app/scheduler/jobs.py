"""Задачи APScheduler: рассылка, follow-up, опрос почты, анализ, напоминания.

Все задачи устойчивы к ошибкам отдельных элементов — падение одного письма
не должно ронять всю задачу.
"""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agent import outreach
from app.agent.analyzer import analyze_email, compose_reply
from app.agent.email_client import fetch_unseen, send_email
from app.agent.pipeline import apply_analysis
from app.bot import keyboards, texts
from app.db.base import async_session
from app.db.enums import MessageDirection, ThreadStatus
from app.db.models import EmailMessage, EmailThread, Opportunity
from app.db.repository import (
    due_reminders,
    opportunities_to_contact,
    threads_deferred_due,
    threads_needing_followup,
)
from config import settings

log = logging.getLogger("scheduler")

# Признаки автоответа — на такие письма агент не отвечает (защита от циклов).
_AUTOREPLY_MARKERS = (
    "auto-reply", "autoreply", "out of office", "автоответ", "no-reply",
    "noreply", "do not reply", "не отвечайте",
)


def _looks_like_autoreply(subject: str) -> bool:
    s = (subject or "").lower()
    return any(m in s for m in _AUTOREPLY_MARKERS)


async def _notify_admin(bot: Bot, text: str) -> None:
    if settings.admin_chat_id:
        try:
            await bot.send_message(settings.admin_chat_id, text)
        except Exception:
            log.exception("Не удалось уведомить админа")


# ── 1. Первичная рассылка ──────────────────────────────────
async def job_send_initial(bot: Bot) -> None:
    async with async_session() as session:
        opps = await opportunities_to_contact(session)
        for opp in opps:
            try:
                msg = await outreach.send_initial(session, opp)
                await session.commit()
                await _notify_admin(bot, msg)
            except Exception:
                await session.rollback()
                log.exception("send_initial failed for opp=%s", opp.id)


# ── 2. Follow-up ───────────────────────────────────────────
async def job_followups(bot: Bot) -> None:
    async with async_session() as session:
        threads = await threads_needing_followup(session, datetime.utcnow())
        for thread in threads:
            # подгружаем связанную возможность
            await session.refresh(thread, ["opportunity"])
            try:
                msg = await outreach.send_followup(session, thread)
                await session.commit()
                await _notify_admin(bot, msg)
            except Exception:
                await session.rollback()
                log.exception("followup failed for thread=%s", thread.id)


# ── 3. Опрос входящих ──────────────────────────────────────
async def job_poll_inbox(bot: Bot) -> None:
    try:
        incoming = await fetch_unseen()
    except Exception:
        log.exception("IMAP poll failed")
        return

    async with async_session() as session:
        for mail in incoming:
            # матчим письмо к возможности по адресу отправителя
            opp = await session.scalar(
                select(Opportunity).where(
                    Opportunity.contact_email == mail.from_addr
                )
            )
            if opp is None:
                continue
            thread = await session.scalar(
                select(EmailThread).where(EmailThread.opportunity_id == opp.id)
            )
            if thread is None:
                continue

            session.add(
                EmailMessage(
                    thread_id=thread.id,
                    direction=MessageDirection.IN,
                    subject=mail.subject,
                    body=mail.body,
                    message_id=mail.message_id,
                )
            )
            thread.status = ThreadStatus.ANSWERED
            thread.last_received_at = datetime.utcnow()
            thread.next_action_at = None  # ответ получен — follow-up не нужен
            await session.commit()


# ── 4. Анализ входящих через DeepSeek ──────────────────────
async def job_analyze(bot: Bot) -> None:
    async with async_session() as session:
        stmt = (
            select(EmailMessage)
            .where(
                EmailMessage.direction == MessageDirection.IN,
                EmailMessage.is_analyzed.is_(False),
            )
            .options(selectinload(EmailMessage.thread))
        )
        messages = list((await session.scalars(stmt)).all())

        for msg in messages:
            try:
                analysis = await analyze_email(msg.subject, msg.body)
                msg.analysis_json = analysis.to_json()
                msg.is_analyzed = True

                opp = await session.get(Opportunity, msg.thread.opportunity_id)
                note = apply_analysis(opp, analysis, msg.thread)

                # Авто-ответ через DeepSeek (кроме отказов и явных автоответов).
                if (
                    analysis.intent != "negative"
                    and opp.contact_email
                    and not _looks_like_autoreply(msg.subject)
                ):
                    reply = await compose_reply(opp.title, msg.subject, msg.body)
                    if reply:
                        full = reply + outreach.SIGNATURE
                        subj = (
                            msg.subject
                            if msg.subject.lower().startswith("re:")
                            else f"Re: {msg.subject}"
                        )
                        mid = await send_email(opp.contact_email, subj, full)
                        session.add(
                            EmailMessage(
                                thread_id=msg.thread.id,
                                direction=MessageDirection.OUT,
                                subject=subj,
                                body=full,
                                message_id=mid,
                            )
                        )
                        note += " · ✉️ отправлен авто-ответ"

                await session.commit()
                await _notify_admin(bot, note)
            except Exception:
                await session.rollback()
                log.exception("analyze failed for msg=%s", msg.id)


# ── 4б. Повторный контакт «отложенных» в назначенную дату ──
async def job_deferred_recontact(bot: Bot) -> None:
    async with async_session() as session:
        threads = await threads_deferred_due(session, datetime.utcnow())
        for thread in threads:
            await session.refresh(thread, ["opportunity"])
            try:
                msg = await outreach.send_recontact(session, thread)
                await session.commit()
                await _notify_admin(bot, msg)
            except Exception:
                await session.rollback()
                log.exception("recontact failed for thread=%s", thread.id)


# ── 5. Напоминания пользователям ───────────────────────────
async def job_reminders(bot: Bot) -> None:
    async with async_session() as session:
        reminders = await due_reminders(session, datetime.utcnow())
        for reminder in reminders:
            opp = await session.get(Opportunity, reminder.opportunity_id)
            try:
                await bot.send_message(
                    reminder.user_id,
                    texts.reminder_fire(opp),
                    reply_markup=keyboards.reminder_fire_kb(opp),
                )
                reminder.is_sent = True
                await session.commit()
            except Exception:
                await session.rollback()
                log.exception("reminder send failed id=%s", reminder.id)


def build_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    # интервалы можно вынести в конфиг; здесь разумные значения по умолчанию
    scheduler.add_job(job_send_initial, "interval", hours=12, args=[bot])
    scheduler.add_job(job_followups, "interval", hours=6, args=[bot])
    scheduler.add_job(job_deferred_recontact, "interval", hours=12, args=[bot])
    scheduler.add_job(job_poll_inbox, "interval", minutes=10, args=[bot])
    scheduler.add_job(job_analyze, "interval", minutes=15, args=[bot])
    scheduler.add_job(job_reminders, "interval", minutes=5, args=[bot])
    return scheduler
