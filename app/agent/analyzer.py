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
    deadline: str | None # ISO-дата дедлайна, если упомянут
    requirements: str | None  # что просят прислать/сделать
    next_action: str     # reply | wait | publish | close
    confidence: float    # 0..1

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


SYSTEM_PROMPT = (
    "Ты — ассистент, который разбирает ответы акселераторов, грантодателей и "
    "компаний на письма-заявки. Проанализируй письмо и верни СТРОГО JSON со "
    "следующими полями:\n"
    '  "intent": один из "positive" | "negative" | "needs_info" | "neutral";\n'
    '  "summary": краткий пересказ ответа на русском (1-2 предложения);\n'
    '  "deadline": дата дедлайна подачи в формате YYYY-MM-DD или null;\n'
    '  "requirements": что от нас просят прислать/сделать, или null;\n'
    '  "next_action": один из "reply" | "wait" | "publish" | "close";\n'
    '  "confidence": число от 0 до 1.\n'
    "Никакого текста вне JSON."
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
            requirements=None,
            next_action="reply",
            confidence=0.0,
        )

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
            requirements=None,
            next_action="reply",
            confidence=0.0,
        )

    return Analysis(
        intent=data.get("intent", "neutral"),
        summary=data.get("summary", ""),
        deadline=_parse_date(data.get("deadline")),
        requirements=data.get("requirements"),
        next_action=data.get("next_action", "reply"),
        confidence=float(data.get("confidence", 0.0)),
    )


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (ValueError, TypeError):
        return None
