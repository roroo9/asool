from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    cohere_api_key: str = ""
    mistral_api_key: str = ""
    openrouter_api_key: str = ""

    # Model roles (provider:model). Change here or via env, never in code.
    page_parser_model: str = "openrouter:google/gemini-3.1-pro-preview"
    page_parser_fallback_model: str = "google:gemini-3.5-flash"
    answer_model: str = "openrouter:google/gemini-3.1-pro-preview"
    answer_fallback_model: str = "openrouter:google/gemini-3.8-flash"
    classifier_model: str = "openrouter:google/gemini-3.8-flash"
    embed_model: str = "openrouter:google/gemini-embedding-2"
    box_model: str = "openrouter:google/gemini-3.8-flash"
    openrouter_budget_usd: float = 25.0
    # spend before the usage log tracked every call (truncated calls, Oct 4): keeps totals honest
    openrouter_spend_offset_usd: float = 0.89
    hard_budget_usd: float = 23.0
    # support gate: minimum dense similarity of the best passage (calibrated in Phase 5)
    support_min_sim: float = 0.55
    # Mushaf verses (approved source outside the book) are offered only when the book's best
    # match is weaker than this, i.e. the book does not cover the question (owner rule, Oct 6).
    external_verses_max_book_sim: float = 0.65
    anthropic_budget_usd: float = 5.0

    cors_origins: str = "http://localhost:3000"
    db_path: str = str(ROOT / "data" / "asool.db")
    daily_budget_usd: float = 1.5
    answer_rate_limit_per_hour: int = 20
    review_token: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
