"""Smoke test for the centralized AURA LLM factory."""

from app.llm import get_llm

llm = get_llm()

response = llm.invoke("What is AURA? Answer in one sentence.")

print(response.content)
