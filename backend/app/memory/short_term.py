"""Short-term conversational session memory for AURA."""

from __future__ import annotations

from typing import Any

# In-memory session store: session_id -> list of turn dicts
_SESSION_MEMORY: dict[str, list[dict[str, str]]] = {}
DEFAULT_MAX_TURNS = 10


def get_history(session_id: str, max_turns: int = DEFAULT_MAX_TURNS) -> list[dict[str, str]]:
    """Retrieve the last N turns for a session; returns list of dict(role=str, content=str)."""
    turns = _SESSION_MEMORY.get(session_id, [])
    return turns[-max_turns:] if turns else []


def append_turn(session_id: str, role: str, content: str) -> None:
    """Append a dialogue turn to the session history."""
    if session_id not in _SESSION_MEMORY:
        _SESSION_MEMORY[session_id] = []
    _SESSION_MEMORY[session_id].append({"role": role, "content": content})


def clear_history(session_id: str) -> None:
    """Clear memory for a given session."""
    if session_id in _SESSION_MEMORY:
        _SESSION_MEMORY[session_id] = []
