"""Подписка пользователя на напоминание о дедлайне."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot import texts
from app.db.base import async_session
from app.db.repository import create_reminder, get_opportunity

router = Router()


@router.callback_query(F.data.startswith("remind:"))
async def set_reminder(callback: CallbackQuery) -> None:
    opp_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        opp = await get_opportunity(session, opp_id)
        if opp is None:
            await callback.answer("Возможность недоступна", show_alert=True)
            return

        reminder = await create_reminder(session, callback.from_user.id, opp)
        await session.commit()

        if reminder is None:
            await callback.answer(texts.reminder_no_deadline(), show_alert=True)
            return

        await callback.answer(
            texts.reminder_set(opp, reminder.remind_at), show_alert=True
        )
