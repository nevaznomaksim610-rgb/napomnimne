"""Админ-команды агента (только для ADMIN_CHAT_ID).

/outreach <категория> | <email> | <название> — создать программу и отправить
первое письмо. Дальше обычный цикл (опрос почты → анализ → обновление дедлайна
и публикация в боте) работает сам.
"""
from __future__ import annotations

import asyncio
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


# Что проверяем на доступность с сервера (host, port).
_NET_TARGETS = [
    ("smtp.mail.ru", 465),
    ("smtp.mail.ru", 587),
    ("imap.mail.ru", 993),
    ("smtp.gmail.com", 587),
    ("imap.gmail.com", 993),
]


async def _probe(host: str, port: int, timeout: float = 8.0) -> tuple[bool, str]:
    try:
        fut = asyncio.open_connection(host, port)
        _, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, ""
    except asyncio.TimeoutError:
        return False, "таймаут"
    except Exception as exc:
        return False, str(exc)[:60]


@router.message(Command("nettest"))
async def cmd_nettest(message: Message) -> None:
    """Проверка доступности почтовых серверов с хостинга (только админ)."""
    if not _is_admin(message):
        return
    await message.answer("⏳ Проверяю подключения с сервера…")
    lines = []
    for host, port in _NET_TARGETS:
        ok, err = await _probe(host, port)
        mark = "✅" if ok else "❌"
        lines.append(f"{mark} <code>{host}:{port}</code>" + (f" — {err}" if err else ""))
    await message.answer("Доступность с сервера:\n\n" + "\n".join(lines))


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
        except Exception as exc:
            await session.rollback()
            log.exception("admin /outreach send failed")
            await message.answer(
                "❌ Не удалось отправить письмо.\n\n"
                f"SMTP: <code>{settings.smtp_host}:{settings.smtp_port}</code>\n"
                f"Отправитель: <code>{settings.email_address or '(пусто)'}</code>\n"
                f"Пароль задан: {'да' if settings.email_password else 'НЕТ'}\n\n"
                f"Ошибка: <code>{exc}</code>"
            )
            return

    await message.answer(
        f"✅ {note}\n\n"
        "Как ответят — агент сам разберёт письмо, и если назовут точную дату, "
        "дедлайн появится в боте, а программа опубликуется."
    )
