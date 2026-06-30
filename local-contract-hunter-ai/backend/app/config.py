from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,"
    "http://127.0.0.1:3000,"
    "https://contract-hunter.vercel.app"
)


@dataclass
class Settings:
    app_name: str = "Local Contract Hunter AI"
    api_prefix: str = "/api"
    cors_origins: list[str] = None
    db_url: str = "sqlite:///./local_contract_hunter.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    cron_webhook_token: str | None = None
    search_delay_seconds: float = 2.0
    playwright_browser_channel: str | None = None
    config_dir: Path = None
    sam_gov_api_key: str | None = None

    def __post_init__(self) -> None:
        origins = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        self.cors_origins = [origin.strip() for origin in origins if origin.strip()]
        self.db_url = os.getenv("DATABASE_URL", self.db_url)
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", self.openai_model)
        self.cron_webhook_token = os.getenv("CRON_WEBHOOK_TOKEN")
        self.search_delay_seconds = float(
            os.getenv("SEARCH_DELAY_SECONDS", str(self.search_delay_seconds))
        )
        browser_channel = os.getenv("PLAYWRIGHT_BROWSER_CHANNEL")
        self.playwright_browser_channel = browser_channel.strip() or None if browser_channel else None
        self.sam_gov_api_key = os.getenv("SAM_GOV_API_KEY")
        base_dir = Path(__file__).resolve().parents[2]
        self.config_dir = base_dir / "config"


settings = Settings()
