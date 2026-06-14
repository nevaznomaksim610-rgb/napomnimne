"""Анализ входящих писем через DeepSeek (OpenAI-совместимый API).

Возвращает структурированный разбор письма, по которому pipeline решает,
какой этап готовности поставить.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime

import httpx

from config import settings


@dataclass
class Analysis:
    """Структурированный результат разбора письма."""

    intent: str          # positive | negative | needs_info | neutral
    summary: str         # краткий пересказ ответа (1-2 предложения, RU)
    deadline: str | None # ISO-дата дедлайна/проведения, если названа ТОЧНО
    recontact_date: str | None  # ISO-дата, когда нас попросили написать снова
    requirements: str | None  # что просят прислать/сделать
    next_action: str     # reply | wait | publish | close
    confidence: float    # 0..1

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


SYSTEM_PROMPT = (
    "Ты — ассистент, который разбирает ответы акселераторов, грантодателей и "
    "компаний на письма-заявки. Сегодня {today}. Проанализируй письмо и верни "
    "СТРОГО JSON со следующими полями:\n"
    '  "intent": один из "positive" | "negative" | "needs_info" | "neutral";\n'
    '  "summary": краткий пересказ ответа на русском (1-2 предложения);\n'
    '  "deadline": ТОЧНАЯ дата дедлайна подачи или проведения в формате '
    "YYYY-MM-DD, если она прямо названа; иначе null;\n"
    '  "recontact_date": если нам НЕ дали точную дату, а попросили написать '
    "позже/ближе к какому-то времени (например «уточняйте в августе», «набор "
    "откроется осенью») — вычисли конкретную дату YYYY-MM-DD, КОГДА нам стоит "
    "написать снова; иначе null;\n"
    '  "requirements": что от нас просят прислать/сделать, или null;\n'
    '  "next_action": один из "reply" | "wait" | "publish" | "close";\n'
    '  "confidence": число от 0 до 1.\n'
    "Если есть точная дата — заполняй deadline, а recontact_date оставь null. "
    "Если точной даты нет, но просят написать позже — заполняй recontact_date. "
    "Никакого текста вне JSON."
)

REPLY_SYSTEM_PROMPT = (
    "Ты пишешь от лица команды проекта вежливый короткий ответ (на русском) на "
    "входящее письмо от акселератора/грантодателя/компании. Контекст: мы ранее "
    "спросили у них актуальные сроки и условия участия в программе «{title}». "
    "Сегодня {today}.\n"
    "Правила ответа по ситуации:\n"
    "- если назвали точную дату — поблагодари и подтверди, что будем держать "
    "сроки на контроле;\n"
    "- если попросили написать позже — поблагодари, скажи, что вернёмся ближе "
    "к названному времени;\n"
    "- если просят прислать информацию/документы — вежливо уточни детали, что "
    "именно нужно;\n"
    "- держись делового, тёплого, краткого тона (3-6 предложений).\n"
    "Верни ТОЛЬКО текст письма без темы, без пояснений и без подписи "
    "(подпись добавится отдельно)."
)


async def analyze_email(subject: str, body: str) -> Analysis:
    """Отправляет письмо в DeepSeek и парсит структурированный ответ.

    При отсутствии ключа или ошибке возвращает безопасный neutral-разбор,
    чтобы pipeline просто оставил тред на ручной разбор.
    """
    if not settings.deepseek_api_key:
        return Analysis(
            intent="neutral",
            summary="(DeepSeek API не настроен — требуется ручной разбор)",
            deadline=None,
            recontact_date=None,
            requirements=None,
            next_action="reply",
            confidence=0.0,
        )

    today = datetime.utcnow().strftime("%Y-%m-%d")
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(today=today)},
            {
                "role": "user",
                "content": f"Тема: {subject}\n\nТекст письма:\n{body}",
            },
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
    except Exception as exc:  # сеть/парсинг/таймаут — не роняем агента
        return Analysis(
            intent="neutral",
            summary=f"(Ошибка анализа: {exc})",
            deadline=None,
            recontact_date=None,
            requirements=None,
            next_action="reply",
            confidence=0.0,
        )

    return Analysis(
        intent=data.get("intent", "neutral"),
        summary=data.get("summary", ""),
        deadline=_parse_date(data.get("deadline")),
        recontact_date=_parse_date(data.get("recontact_date")),
        requirements=data.get("requirements"),
        next_action=data.get("next_action", "reply"),
        confidence=float(data.get("confidence", 0.0)),
    )


async def compose_reply(title: str, subject: str, body: str) -> str | None:
    """Сгенерировать текст ответа на входящее письмо через DeepSeek.

    Возвращает текст письма (без подписи) или None, если ключа нет/ошибка —
    тогда авто-ответ просто не отправляется.
    """
    if not settings.deepseek_api_key:
        return None

    today = datetime.utcnow().strftime("%Y-%m-%d")
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {
                "role": "system",
                "content": REPLY_SYSTEM_PROMPT.format(title=title, today=today),
            },
            {
                "role": "user",
                "content": f"Тема: {subject}\n\nТекст письма:\n{body}",
            },
        ],
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            return text or None
    except Exception:
        return None


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (ValueError, TypeError):
        return None
