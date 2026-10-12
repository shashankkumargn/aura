"""Provider-agnostic chat model factory for AURA."""

from __future__ import annotations

import os
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def get_llm(role: str = "default") -> BaseChatModel:
    """Return the configured LangChain chat model for the active provider with optional role override."""
    model_name = settings.model_name
    if role == "router":
        router_model = os.getenv("ROUTER_MODEL_NAME")
        if router_model:
            model_name = router_model

    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing.")
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model_name or "llama-3.3-70b-versatile",
            api_key=settings.groq_api_key,
            temperature=0,
        )

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is missing.")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name or "gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0,
        )

    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is missing.")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name or "claude-3-5-haiku-latest",
            api_key=settings.anthropic_api_key,
            temperature=0,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
