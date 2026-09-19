"""Question builders. Keep packs on these helpers so criteria stay legal."""

from __future__ import annotations

from typing import Any, Mapping


GATEWAY_MAX_QUESTIONS = 32
GATEWAY_MAX_CHOICE_OPTIONS = 64
GATEWAY_MIN_SCORE_LEVELS = 2
GATEWAY_MAX_SCORE_LEVELS = 10
SHARED_INPUT_TOKEN_BUDGET = 32_000
DEFAULT_MODEL = "jev-latest"
GATEWAY_URL = "https://api.experientiallabs.ai/v1/systemone"


class SchemaError(ValueError):
    pass


def choice(instructions: str, criteria: Mapping[str, str]) -> dict[str, Any]:
    if not criteria:
        raise SchemaError("choice needs at least one option")
    if len(criteria) > GATEWAY_MAX_CHOICE_OPTIONS:
        raise SchemaError(f"choice max {GATEWAY_MAX_CHOICE_OPTIONS} options")
    return {
        "type": "choice",
        "instructions": instructions,
        "criteria": dict(criteria),
    }


def noul(
    instructions: str,
    true: str | None = None,
    false: str | None = None,
) -> dict[str, Any]:
    q: dict[str, Any] = {"type": "noul", "instructions": instructions}
    if true is not None or false is not None:
        criteria: dict[str, str] = {}
        if true is not None:
            criteria["true"] = true
        if false is not None:
            criteria["false"] = false
        q["criteria"] = criteria
    return q


def score(instructions: str, levels: list[str]) -> dict[str, Any]:
    n = len(levels)
    if n < GATEWAY_MIN_SCORE_LEVELS or n > GATEWAY_MAX_SCORE_LEVELS:
        raise SchemaError(
            f"score needs {GATEWAY_MIN_SCORE_LEVELS}–{GATEWAY_MAX_SCORE_LEVELS} levels"
        )
    return {
        "type": "score",
        "instructions": instructions,
        "criteria": list(levels),
    }


def validate_questions(questions: Mapping[str, Any]) -> None:
    """Check a question map against the gateway limits.

    Builders keep packs legal; this also guards raw dicts handed in by a caller.
    """
    if not isinstance(questions, Mapping) or not questions:
        raise SchemaError("questions must be a non-empty map")
    if len(questions) > GATEWAY_MAX_QUESTIONS:
        raise SchemaError(f"max {GATEWAY_MAX_QUESTIONS} questions per request")
    for qid, q in questions.items():
        if not isinstance(qid, str) or not qid:
            raise SchemaError("question ids must be non-empty strings")
        if not isinstance(q, dict) or q.get("type") not in {"choice", "noul", "score"}:
            raise SchemaError(f"{qid}: type must be choice|noul|score")
        if not q.get("instructions"):
            raise SchemaError(f"{qid}: instructions required")
        if q["type"] == "choice":
            criteria = q.get("criteria")
            if not isinstance(criteria, dict) or not criteria:
                raise SchemaError(f"{qid}: choice needs a non-empty criteria map")
            if len(criteria) > GATEWAY_MAX_CHOICE_OPTIONS:
                raise SchemaError(
                    f"{qid}: choice max {GATEWAY_MAX_CHOICE_OPTIONS} options"
                )
        if q["type"] == "score":
            levels = q.get("criteria")
            if not isinstance(levels, list) or not levels:
                raise SchemaError(f"{qid}: score needs a non-empty criteria list")
            if not GATEWAY_MIN_SCORE_LEVELS <= len(levels) <= GATEWAY_MAX_SCORE_LEVELS:
                raise SchemaError(
                    f"{qid}: score needs {GATEWAY_MIN_SCORE_LEVELS}–"
                    f"{GATEWAY_MAX_SCORE_LEVELS} levels"
                )
        if q["type"] == "noul" and "criteria" in q:
            criteria = q["criteria"]
            if not isinstance(criteria, dict):
                raise SchemaError(f"{qid}: noul criteria must be a map")
            if not set(criteria) <= {"true", "false"}:
                raise SchemaError(f"{qid}: noul criteria keys must be true|false")
