"""/start и выбор категории."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards, texts
from app.db.base import async_session
from app.db.enums import Category
from app.db.repository import list_published, upsert_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session() as session:
        await upsert_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        await session.commit()
    await message.answer(texts.START, reply_markup=keyboards.categories_kb())


@router.callback_query(F.data == "home")
async def go_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        texts.CHOOSE_CATEGORY, reply_markup=keyboards.categories_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery) -> None:
    category = Category(callback.data.split(":", 1)[1])
    async with async_session() as session:
        items = await list_published(session, category)

    if not items:
        await callback.message.edit_text(
            f"{category.title}\n\n{texts.EMPTY_CATEGORY}",
            reply_markup=keyboards.catalog_kb(category, []),
        )
    else:
        await callback.message.edit_text(
            f"{category.title}\n\n{texts.CHOOSE_CATEGORY}",
            reply_markup=keyboards.catalog_kb(category, items),
        )
    await callback.answer()
