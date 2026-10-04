from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    cohere_api_key: str = ""

    cors_origins: str = "http://localhost:3000"
    db_path: str = str(ROOT / "data" / "asool.db")
    daily_budget_usd: float = 3.0
    answer_rate_limit_per_hour: int = 20
    review_token: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
