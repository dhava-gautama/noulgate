"""Offline transport: answer the question pack from the state text alone.

No network, no key, no charge. The answer shapes match the wire schema so the
dry-run path and the live path are interchangeable for every caller.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from . import schemas

_TOKEN = re.compile(r"[a-z0-9_]+")

# Read-only, local inspection.
_READ = ("read", "open", "cat", "grep", "glob", "ls", "file", "inspect", "diff", "show")
# Finding a fact that is not on disk yet.
_SEARCH = ("search", "google", "lookup", "look_up", "web", "docs", "documentation", "find", "fetch")
# Running a command on the machine.
_SHELL = (
    "shell",
    "bash",
    "sh",
    "zsh",
    "terminal",
    "run",
    "exec",
    "command",
    "test",
    "unittest",
    "pytest",
    "build",
    "compile",
    "make",
    "install",
    "pip",
    "npm",
    "cargo",
    "go",
    "docker",
    "git",
)
# Loading or driving a page.
_BROWSER = ("browser", "playwright", "selenium", "page", "click", "url", "http", "curl", "wget")
# Handing the decision back to a person.
_REVIEW = ("review", "approve", "approval", "sign", "signoff", "confirm", "human", "operator", "ask")
# Anything that changes state, spends money, or leaves the machine.
_SIDE_EFFECT = (
    "write",
    "patch",
    "apply",
    "edit",
    "commit",
    "push",
    "deploy",
    "delete",
    "remove",
    "rm",
    "mv",
    "chmod",
    "chown",
    "install",
    "post",
    "upload",
    "send",
    "publish",
    "drop",
    "kill",
    "restart",
    "curl",
    "wget",
)

# Writing or modifying code.
_EDIT = ("edit", "write", "patch", "refactor", "implement", "fix", "bug", "code", "rename", "migrate")
# Judging something that already exists.
_JUDGE = ("review", "diff", "judge", "audit", "critique", "verify", "regression")
# Breaking work into steps without doing it.
_PLAN = ("plan", "design", "architecture", "blueprint", "spec", "proposal")
# Multi-source investigation.
_RESEARCH = ("research", "investigate", "survey", "compare", "landscape", "benchmark")
# Facts that are already on disk.
_LOCAL_FACT = ("file", "repo", "workspace", "path", "directory", "code", "source", "tree", "module")

# Words that suggest a written procedure should be followed.
_PROCEDURE = (
    "skill",
    "playbook",
    "runbook",
    "procedure",
    "checklist",
    "workflow",
    "guideline",
    "convention",
    "install",
    "deploy",
    "migrate",
    "audit",
)
_CHATTY = ("hey", "hi", "hello", "thanks", "thank", "you", "ok", "okay", "please", "how", "are", "what", "why", "who")

# A goal that promises not to touch anything.
_NEGATED_EFFECT = ("no diff", "no change", "read only", "read-only", "nothing to change", "no writes", "dry run")


class DryRunError(ValueError):
    pass


def state_text(state: Any) -> str:
    """Flatten a state value into the text the fixture judges."""
    if isinstance(state, str):
        return state
    if isinstance(state, Mapping):
        parts: list[str] = []
        for key, value in state.items():
            parts.append(f"{key} {state_text(value)}")
        return " ".join(parts)
    if isinstance(state, (list, tuple)):
        return " ".join(state_text(item) for item in state)
    return str(state)


def primary_text(state: Any) -> str:
    """The part of the state that describes the task, without the diff/test tail.

    ``compress_state`` always fills ``diff`` and ``test_summary``; those defaults
    must not decide which tool a turn needs.
    """
    if isinstance(state, Mapping):
        goal = state.get("goal")
        if goal is not None:
            return f"{state_text(goal)} {state.get('intended_tool', '')}"
    return state_text(state)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _mentions(tokens: set[str], words: tuple[str, ...]) -> bool:
    return any(word in tokens for word in words)


def _looks_like_smalltalk(tokens: set[str], text: str) -> bool:
    if len(text.split()) > 25:
        return False
    if _mentions(tokens, _READ + _SEARCH + _SHELL + _BROWSER + _EDIT):
        return False
    return len(tokens) <= 12 and _mentions(tokens, _CHATTY)


def _looks_like_procedure(tokens: set[str]) -> bool:
    return _mentions(tokens, _PROCEDURE)


def _looks_green(tokens: set[str]) -> bool:
    return bool({"pass", "passed", "passing", "green", "ok"} & tokens)


def _family(tokens: set[str], intended: str) -> tuple[str, float]:
    """Return the tool family and a side-effect noul for it."""
    if intended and intended.lower() not in {"none", "no", ""}:
        lowered = intended.lower()
        if any(word in lowered for word in _REVIEW):
            return "review", 0.2
        if any(word in lowered for word in _BROWSER):
            return "browser", 0.5
        if any(word in lowered for word in _SHELL):
            return "shell", 0.6
        if any(word in lowered for word in _SEARCH):
            return "search", 0.2
        if any(word in lowered for word in _READ):
            return "read", 0.1
    if _mentions(tokens, _REVIEW):
        return "review", 0.2
    if _mentions(tokens, _BROWSER):
        return "browser", 0.5
    if _mentions(tokens, _SHELL):
        return "shell", 0.6
    if _mentions(tokens, _SEARCH):
        return "search", 0.2
    if _mentions(tokens, _READ):
        return "read", 0.1
    return "none", 0.05


def _side_effect(tokens: set[str], text: str, family: str) -> float:
    if any(phrase in text.lower() for phrase in _NEGATED_EFFECT):
        return 0.1
    if _mentions(tokens, _SIDE_EFFECT):
        return 0.85
    return {"shell": 0.6, "browser": 0.5, "read": 0.1}.get(family, 0.05)


def _noul_answers(task: str, text: str, intended: str) -> dict[str, Any]:
    tokens = _tokens(task)
    family, family_effect = _family(tokens, intended)
    side_effect = max(family_effect, _side_effect(tokens, task, family)) if family != "none" else _side_effect(
        tokens, task, family
    )
    smalltalk = _looks_like_smalltalk(tokens, task)
    local_fact = _mentions(tokens, _LOCAL_FACT)
    need_tool = 0.15 if smalltalk else (0.85 if family != "none" else 0.35)
    need_evidence = 0.1 if smalltalk else (0.8 if family in {"search", "browser"} else (0.35 if local_fact else 0.3))
    full = _tokens(text)
    return {
        "need_tool": need_tool,
        "need_new_evidence": need_evidence,
        "side_effect": side_effect,
        "need_skill": 0.15 if smalltalk else (0.8 if _looks_like_procedure(tokens) else 0.3),
        "just_talk": 0.9 if smalltalk else 0.2,
        "cheap_ok": 0.8 if smalltalk else (0.2 if _mentions(tokens, _EDIT + _PLAN + _RESEARCH) else 0.55),
        "needs_reasoning": 0.15 if smalltalk else (0.8 if _mentions(tokens, _EDIT + _PLAN) else 0.35),
        "context_fat": 0.6 if len(text) > 2000 else 0.3,
        "tests_support": 0.7 if _looks_green(full) else 0.3,
        "safe_to_apply": 0.2 if _mentions(full, ("auth", "secret", "deploy", "data", "prod")) else 0.6,
    }


def _choice_answers(task: str, intended: str) -> dict[str, Any]:
    tokens = _tokens(task)
    family, _ = _family(tokens, intended)
    smalltalk = _looks_like_smalltalk(tokens, task)
    if smalltalk:
        task_kind = "chat"
    elif _mentions(tokens, _RESEARCH):
        task_kind = "research"
    elif _mentions(tokens, _PLAN):
        task_kind = "plan"
    elif _mentions(tokens, _EDIT):
        task_kind = "edit"
    elif _mentions(tokens, _JUDGE):
        task_kind = "review"
    elif family in {"read", "search", "browser"}:
        task_kind = "lookup"
    else:
        task_kind = "chat"

    if smalltalk:
        tier = "nano"
    elif _mentions(tokens, _EDIT + _PLAN):
        tier = "frontier" if len(task) > 1500 else "mid"
    elif task_kind == "research":
        tier = "small"
    elif task_kind in {"lookup", "chat"}:
        tier = "small"
    else:
        tier = "mid"

    if smalltalk:
        skill_action = "none"
    elif _looks_like_procedure(tokens):
        skill_action = "view_one"
    else:
        skill_action = "none"

    if _mentions(tokens, ("auth", "secret", "deploy", "prod", "delete", "push")):
        action = "ask"
    else:
        action = "show"
    return {
        "tool_family": family,
        "skill_action": skill_action,
        "task_kind": task_kind,
        "model_tier": tier,
        "action": action,
    }


def _score_answers(text: str) -> dict[str, Any]:
    tokens = _tokens(text)
    if _mentions(tokens, ("auth", "secret", "deploy", "prod")):
        risk = 2.0
    elif _mentions(tokens, _SIDE_EFFECT):
        risk = 1.0
    else:
        risk = 0.0
    return {"risk": risk}


def fixture_response(state: Any, questions: Mapping[str, Any]) -> dict[str, Any]:
    """Build a schema-shaped System One response for ``questions`` without a network call."""
    schemas.validate_questions(questions)
    text = state_text(state)
    task = primary_text(state)
    mapping = state if isinstance(state, Mapping) else {}
    intended = str(mapping.get("intended_tool", ""))
    nouls = _noul_answers(task, text, intended)
    choices = _choice_answers(task, intended)
    scores = _score_answers(text)

    answers: dict[str, Any] = {}
    for qid, question in questions.items():
        kind = question["type"]
        if kind == "noul":
            answers[qid] = {"type": "noul", "noul": nouls.get(qid, 0.5)}
        elif kind == "choice":
            criteria = list(question["criteria"])
            picked = choices.get(qid, criteria[0])
            if picked not in criteria:
                picked = criteria[0]
            share = 0.6
            rest = (1.0 - share) / max(1, len(criteria) - 1)
            probabilities = {name: (share if name == picked else rest) for name in criteria}
            answers[qid] = {
                "type": "choice",
                "choice": picked,
                "confidence": share,
                "probabilities": probabilities,
            }
        elif kind == "score":
            levels = list(question["criteria"])
            value = float(min(scores.get(qid, 0.0), len(levels) - 1))
            answers[qid] = {
                "type": "score",
                "score": value,
                "confidence": 0.6,
                "legend": {str(index): level for index, level in enumerate(levels)},
                "probabilities": _score_probabilities(value, len(levels)),
            }
        else:  # pragma: no cover - validate_questions rejects this first
            raise DryRunError(f"{qid}: unknown question type {kind!r}")

    return {
        "model": schemas.DEFAULT_MODEL,
        "usage": {"input_tokens": max(1, len(text) // 4), "output_tokens": 0},
        "answers": answers,
    }


def _score_probabilities(value: float, levels: int) -> dict[str, float]:
    """Spread probability across the levels, peaking at ``value``."""
    weights = [1.0 / (1.0 + abs(level - value)) for level in range(levels)]
    total = sum(weights)
    return {str(level): round(weight / total, 4) for level, weight in enumerate(weights)}


def make_transport(state: Any, questions: Mapping[str, Any]):
    """Return a ``JevClient`` transport that answers from ``state`` with no network."""

    def transport(url: str, headers: dict[str, str], body: bytes, timeout_s: float) -> tuple[int, str]:
        import json

        return 200, json.dumps(fixture_response(state, questions), ensure_ascii=False)

    return transport
