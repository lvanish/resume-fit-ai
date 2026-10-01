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
    # Local extraction. The public score path keeps using raw text unless this is enabled.
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:1.5b-instruct-q5_K_M"
    llm_timeout_seconds: float = 300
    llm_num_predict: int = 512
    llm_num_ctx: int = 2048
    llm_extraction_enabled: bool = False
    # Requirement-level scoring. False keeps the broad Laya baseline on the public score path.
    requirement_matching_enabled: bool = False
    requirement_questions_per_batch: int | None = None
    requirement_weight_required_skills: float = 0.55
    requirement_weight_responsibilities: float = 0.15
    requirement_weight_experience: float = 0.15
    requirement_weight_role: float = 0.10
    requirement_weight_preferred_skills: float = 0.05

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
