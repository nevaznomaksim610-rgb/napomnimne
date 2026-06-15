"""Напоминания: выбор «когда», ввод точной даты (FSM), список и отмена."""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards, texts
from app.db.base import async_session
from app.db.repository import (
    CUSTOM_OFFSET,
    add_reminder,
    delete_reminder,
    get_opportunity,
    list_user_reminders,
    upsert_user,
)
from app.timeutil import deadline_remind_utc, now_utc, to_utc
from config import settings

router = Router()


class RemindStates(StatesGroup):
    waiting_date = State()


def _remind_at_for_kind(opp, kind: str) -> tuple[datetime | None, int]:
    """По коду варианта вернуть (момент UTC, offset_days). None — некорректный код."""
    if kind.startswith("n"):
        days = int(kind[1:])
        return now_utc() + timedelta(days=days), CUSTOM_OFFSET
    if kind.startswith("d") and opp.deadline is not None:
        offset = int(kind[1:])
        return deadline_remind_utc(opp.deadline, offset), offset
    return None, CUSTOM_OFFSET


def _parse_user_date(raw: str) -> datetime | None:
    """Текст пользователя → момент UTC. Без времени — час по умолчанию (МСК)."""
    raw = raw.strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            local = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if fmt == "%d.%m.%Y":
            local = local.replace(hour=settings.reminder_hour, minute=0)
        return to_utc(local)
    return None


# ── Меню «когда напомнить» ─────────────────────────────────
@router.callback_query(F.data.startswith("remopts:"))
async def show_reminder_options(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    opp_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        opp = await get_opportunity(session, opp_id)
    if opp is None or not opp.is_published:
        await callback.answer("Возможность недоступна", show_alert=True)
        return
    await callback.message.edit_text(
        texts.reminder_prompt(opp), reply_markup=keyboards.reminder_options_kb(opp)
    )
    await callback.answer()


# ── Постановка напоминания (пресет или запуск ввода даты) ──
@router.callback_query(F.data.startswith("rem:"))
async def set_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    _, raw_id, kind = callback.data.split(":", 2)
    opp_id = int(raw_id)
    async with async_session() as session:
        opp = await get_opportunity(session, opp_id)
    if opp is None or not opp.is_published:
        await callback.answer("Возможность недоступна", show_alert=True)
        return

    if kind == "date":
        await state.set_state(RemindStates.waiting_date)
        await state.update_data(opp_id=opp_id)
        await callback.message.edit_text(texts.ASK_DATE)
        await callback.answer()
        return

    remind_at, offset = _remind_at_for_kind(opp, kind)
    if remind_at is None:
        await callback.answer("Не удалось поставить напоминание", show_alert=True)
        return

    await _create_and_confirm(callback, opp_id, remind_at, offset, edit=True)


# ── Ввод точной даты (FSM) ─────────────────────────────────
@router.message(RemindStates.waiting_date)
async def receive_date(message: Message, state: FSMContext) -> None:
    remind_at = _parse_user_date(message.text or "")
    if remind_at is None:
        await message.answer(texts.DATE_BAD)
        return
    if remind_at <= now_utc():
        await message.answer(texts.DATE_PAST)
        return

    data = await state.get_data()
    opp_id = data.get("opp_id")
    await state.clear()
    if opp_id is None:
        return
    await _create_and_confirm(message, opp_id, remind_at, CUSTOM_OFFSET, edit=False)


async def _create_and_confirm(
    event: CallbackQuery | Message,
    opp_id: int,
    remind_at: datetime,
    offset: int,
    edit: bool,
) -> None:
    user = event.from_user
    async with async_session() as session:
        opp = await get_opportunity(session, opp_id)
        if opp is None:
            return
        await upsert_user(session, user.id, user.username, user.first_name)
        await add_reminder(session, user.id, opp_id, remind_at, offset)
        await session.commit()
        text = texts.reminder_set(opp, remind_at)

    if edit:
        await event.message.edit_text(text, reply_markup=keyboards.reminder_done_kb())
        await event.answer("Напоминание поставлено 🔔")
    else:
        await event.answer(text, reply_markup=keyboards.reminder_done_kb())


# ── Мои напоминания ────────────────────────────────────────
@router.callback_query(F.data == "myrem")
async def my_reminders(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _render_my_reminders(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("remcancel:"))
async def cancel_reminder(callback: CallbackQuery) -> None:
    reminder_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        ok = await delete_reminder(session, reminder_id, callback.from_user.id)
        await session.commit()
    await callback.answer(texts.REMINDER_CANCELLED if ok else "Уже отменено")
    await _render_my_reminders(callback)


async def _render_my_reminders(callback: CallbackQuery) -> None:
    async with async_session() as session:
        reminders = await list_user_reminders(session, callback.from_user.id)

    if not reminders:
        await callback.message.edit_text(
            texts.MY_REMINDERS_EMPTY, reply_markup=keyboards.reminder_done_kb()
        )
        return
    await callback.message.edit_text(
        texts.MY_REMINDERS_TITLE, reply_markup=keyboards.my_reminders_kb(reminders)
    )
