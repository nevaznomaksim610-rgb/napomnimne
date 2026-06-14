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

    # Параметры рассылки/напоминаний
    followup_delay_days: int = 3
    max_followups: int = 2
    reminder_offset_days: int = 7


settings = Settings()
