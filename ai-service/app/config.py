from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """External configuration for the AI service.

    LAYA_MODEL selects the Laya checkpoint name passed to Router.predict.
    LAYA_CHECKPOINT, when set, is a Hugging Face revision for that checkpoint.
    """

    laya_model: str = "typed-decisions"
    laya_checkpoint: str | None = None
    # Combined resume + job-description token budget. Unset uses the checkpoint
    # limit minus laya_token_safety_margin.
    laya_input_token_budget: int | None = None
    laya_token_safety_margin: int = 48

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
