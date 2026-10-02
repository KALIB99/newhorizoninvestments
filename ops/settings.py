"""The only place secrets are read. Loaded from .env; never logged, never repr'd."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    live_trading: str = Field("0", alias="LIVE_TRADING")

    binance_api_key: SecretStr | None = Field(None, alias="BINANCE_API_KEY")
    binance_api_secret: SecretStr | None = Field(None, alias="BINANCE_API_SECRET")
    bybit_api_key: SecretStr | None = Field(None, alias="BYBIT_API_KEY")
    bybit_api_secret: SecretStr | None = Field(None, alias="BYBIT_API_SECRET")

    cryptopanic_token: SecretStr | None = Field(None, alias="CRYPTOPANIC_TOKEN")
    newsapi_key: SecretStr | None = Field(None, alias="NEWSAPI_KEY")

    telegram_bot_token: SecretStr | None = Field(None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(None, alias="TELEGRAM_CHAT_ID")

    logs_dir: Path = Path("ops/logs")
    reports_dir: Path = Path("ops/reports")

    def exchange_credentials(self, exchange: str) -> dict[str, str]:
        key = getattr(self, f"{exchange}_api_key", None)
        sec = getattr(self, f"{exchange}_api_secret", None)
        if not key or not sec:
            return {}
        return {"apiKey": key.get_secret_value(), "secret": sec.get_secret_value()}

    def __repr__(self) -> str:  # belt and braces: never leak via repr/logging
        return "Settings(<redacted>)"


def get_settings() -> Settings:
    return Settings()
