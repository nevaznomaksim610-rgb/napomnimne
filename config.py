"""Загрузка настроек из .env через pydantic-settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    bot_token: str = ""
    admin_chat_id: int = 0

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Email
    email_address: str = ""
    email_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993

    # DB
    database_url: str = "sqlite+aiosqlite:///./bot.db"

    # Напоминания контактам (агент): раз в неделю спрашивает про сроки, пока не
    # получит точную дату или дату «напишите позже». followup_max_count —
    # предохранитель: сколько максимум писем-напоминаний слать (0 = без лимита,
    # писать вечно). По умолчанию 12 ≈ 3 месяца еженедельных писем.
    followup_interval_days: int = 7
    followup_max_count: int = 12

    # Часовой пояс пользователей: напоминания считаются и показываются в нём,
    # в БД всё хранится в UTC. reminder_hour — час по умолчанию, в который
    # приходят напоминания «за N дней до дедлайна» и без указанного времени.
    timezone: str = "Europe/Moscow"
    reminder_hour: int = 9

    # Персона агента: от чьего лица пишутся письма в программы. Это обычный
    # студент, которому интересно, когда следующий набор. Меняется через .env.
    agent_name: str = "Кирилл"
    agent_affiliation: str = "студент ВШЭ"


settings = Settings()
