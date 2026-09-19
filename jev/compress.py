"""Build a compact state blob. Never dump a repository."""

from __future__ import annotations

from typing import Any


MAX_DIFF_CHARS = 6_000
MAX_TEST_CHARS = 2_000


def compress_state(
    *,
    goal: str,
    intended_tool: str | None = None,
    diff: str | None = None,
    test_summary: str | None = None,
    session_model: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "goal": goal.strip(),
        "intended_tool": intended_tool or "none",
        "session_model": session_model or "unchanged",
        "diff": _clip(diff or "no diff", MAX_DIFF_CHARS),
        "test_summary": _clip(test_summary or "tests not run", MAX_TEST_CHARS),
    }
    if extra:
        state["extra"] = extra
    return state


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 18] + "\n…[truncated]"
