"""Карточка возможности."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot import keyboards, texts
from app.db.base import async_session
from app.db.repository import get_opportunity

router = Router()


@router.callback_query(F.data.startswith("opp:"))
async def show_opportunity(callback: CallbackQuery) -> None:
    opp_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        opp = await get_opportunity(session, opp_id)

    if opp is None or not opp.is_published:
        await callback.answer("Возможность недоступна", show_alert=True)
        return

    await callback.message.edit_text(
        texts.opportunity_card(opp),
        reply_markup=keyboards.opportunity_kb(opp),
        disable_web_page_preview=False,
    )
    await callback.answer()
