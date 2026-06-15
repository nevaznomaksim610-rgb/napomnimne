"""Почтовый клиент агента: отправка (SMTP) и чтение ответов (IMAP).

IMAP-часть синхронная (imaplib) и оборачивается в поток, чтобы не блокировать
event loop. Этого достаточно для периодического опроса по расписанию.
"""
from __future__ import annotations

import asyncio
import email
import imaplib
from dataclasses import dataclass
from email.header import decode_header
from email.message import EmailMessage as PyEmailMessage

import aiosmtplib
import httpx

from config import settings


@dataclass
class IncomingEmail:
    from_addr: str
    subject: str
    body: str
    message_id: str | None


async def send_email(to_addr: str, subject: str, body: str) -> str | None:
    """Отправить письмо. Возвращает Message-ID/идентификатор отправки.

    Если задан email_api_key — шлём через HTTP-API провайдера (Railway
    блокирует SMTP). Иначе — обычный SMTP (локальная разработка).
    """
    if settings.email_api_key:
        return await _send_via_api(to_addr, subject, body)
    return await _send_via_smtp(to_addr, subject, body)


async def _send_via_smtp(to_addr: str, subject: str, body: str) -> str | None:
    msg = PyEmailMessage()
    msg["From"] = settings.email_address
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.email_address,
        password=settings.email_password,
        use_tls=settings.smtp_port == 465,
        start_tls=settings.smtp_port == 587,
    )
    return msg["Message-ID"]


async def _send_via_api(to_addr: str, subject: str, body: str) -> str | None:
    """Отправка через Brevo HTTP-API. From и Reply-To = наш ящик, чтобы
    ответы приходили на mail.ru и читались по IMAP."""
    if settings.email_api_provider != "brevo":
        raise ValueError(f"Неизвестный email_api_provider: {settings.email_api_provider}")

    payload = {
        "sender": {"email": settings.email_address, "name": settings.agent_name},
        "to": [{"email": to_addr}],
        "replyTo": {"email": settings.email_address},
        "subject": subject,
        "textContent": body,
    }
    headers = {
        "api-key": settings.email_api_key,
        "content-type": "application/json",
        "accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(settings.email_api_url, json=payload, headers=headers)
        if resp.status_code >= 400:
            # Brevo кладёт причину в тело — показываем её, а не голый код.
            raise RuntimeError(f"Brevo {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
    return data.get("messageId")


async def fetch_unseen() -> list[IncomingEmail]:
    """Прочитать непрочитанные письма из INBOX (в отдельном потоке)."""
    return await asyncio.to_thread(_fetch_unseen_sync)


def _fetch_unseen_sync() -> list[IncomingEmail]:
    results: list[IncomingEmail] = []
    with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port) as imap:
        imap.login(settings.email_address, settings.email_password)
        imap.select("INBOX")
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return results
        for num in data[0].split():
            status, msg_data = imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            results.append(
                IncomingEmail(
                    from_addr=_addr(msg.get("From", "")),
                    subject=_decode(msg.get("Subject", "")),
                    body=_extract_body(msg),
                    message_id=msg.get("Message-ID"),
                )
            )
    return results


def _decode(value: str) -> str:
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _addr(value: str) -> str:
    return email.utils.parseaddr(value)[1].lower()


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""
