"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    """Typed runtime settings for the AURA backend."""

    llm_provider: str = Field(default="openai")
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    model_name: str | None = None


def get_settings() -> Settings:
    """Build Settings from the current process environment."""
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        model_name=os.getenv("MODEL_NAME") or None,
    )


settings: Settings = get_settings()
