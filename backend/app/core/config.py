from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "postgresql+psycopg://intakeflow:intakeflow@localhost:5432/intakeflow"
    redis_url: str = "redis://localhost:6379/0"
    app_origin: str = "http://localhost:5173"
    secure_cookies: bool = False
    session_hours: int = Field(default=24, ge=1, le=168)
    demo_accounts_enabled: bool = False
    ai_provider: str = "demo"
    openai_api_key: str = ""
    openai_model: str = ""
    ai_timeout_seconds: float = Field(default=45, gt=0, le=120)
    ai_max_output_tokens: int = Field(default=2200, ge=500, le=8000)
    ai_max_input_chars: int = Field(default=24000, ge=1000, le=40000)
    ai_max_calls: int = 4
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)
    job_lease_seconds: int = Field(default=300, ge=30)

    @model_validator(mode="after")
    def production_safety(self):
        if self.ai_provider not in {"demo", "openai"}:
            raise ValueError("AI_PROVIDER must be demo or openai")
        if self.ai_max_calls not in range(1, 5):
            raise ValueError("AI_MAX_CALLS must be between 1 and 4")
        if self.job_lease_seconds < self.ai_timeout_seconds * self.ai_max_calls + 30:
            raise ValueError("Job lease must cover the total model timeout budget plus 30 seconds")
        if self.environment == "production" and (
            self.demo_accounts_enabled or not self.secure_cookies or self.ai_provider == "demo"
        ):
            raise ValueError(
                "Production requires secure cookies, live AI, and disabled demo accounts"
            )
        return self

    @property
    def checkpoint_url(self):
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_settings():
    return Settings()
