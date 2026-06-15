"""Админ-команды агента (только для ADMIN_CHAT_ID).

/outreach <категория> | <email> | <название> — создать программу и отправить
первое письмо. Дальше обычный цикл (опрос почты → анализ → обновление дедлайна
и публикация в боте) работает сам.
"""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.agent import outreach
from app.db.base import async_session
from app.db.enums import Category, OutreachStage
from app.db.models import Opportunity
from config import settings

router = Router()
log = logging.getLogger("admin")

# Русские псевдонимы категорий — чтобы не писать английские значения enum.
_CATEGORY_ALIASES = {
    "accelerator": Category.ACCELERATOR,
    "акселератор": Category.ACCELERATOR,
    "grant": Category.GRANT,
    "грант": Category.GRANT,
    "leadership": Category.LEADERSHIP,
    "лидерская": Category.LEADERSHIP,
    "ambassador": Category.AMBASSADOR,
    "амбассадор": Category.AMBASSADOR,
}

_USAGE = (
    "Формат:\n"
    "<code>/outreach категория | email | название</code>\n\n"
    "Категории: акселератор, грант, лидерская, амбассадор\n"
    "Пример:\n"
    "<code>/outreach акселератор | test@mail.ru | Сбер 500</code>"
)


def _is_admin(message: Message) -> bool:
    return bool(settings.admin_chat_id) and message.from_user.id == settings.admin_chat_id


@router.message(Command("outreach"))
async def cmd_outreach(message: Message, command: CommandObject) -> None:
    if not _is_admin(message):
        return  # молча игнорируем не-админов

    parts = [p.strip() for p in (command.args or "").split("|")]
    if len(parts) != 3 or not all(parts):
        await message.answer(_USAGE)
        return

    cat_raw, email, title = parts
    category = _CATEGORY_ALIASES.get(cat_raw.lower())
    if category is None:
        await message.answer("Неизвестная категория.\n\n" + _USAGE)
        return

    async with async_session() as session:
        opp = Opportunity(
            category=category,
            title=title,
            contact_email=email,
            stage=OutreachStage.NEW,
            is_published=False,
        )
        session.add(opp)
        await session.flush()
        try:
            note = await outreach.send_initial(session, opp)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("admin /outreach send failed")
            await message.answer("❌ Не удалось отправить письмо (см. логи).")
            return

    await message.answer(
        f"✅ {note}\n\n"
        "Как ответят — агент сам разберёт письмо, и если назовут точную дату, "
        "дедлайн появится в боте, а программа опубликуется."
    )
