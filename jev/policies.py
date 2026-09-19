"""Turn a System One answer map into one advice word an agent can act on.

Advice is a suggestion, never an authorisation. A caller that treats
``apply_advice_only`` as permission to mutate is misusing this module.
"""

from __future__ import annotations

from typing import Any, Mapping

# A noul at or above this is read as "yes"; at or below NEGATIVE as "no".
POSITIVE = 0.5
STRONG_POSITIVE = 0.7
NEGATIVE = 0.35
# Score rubrics are indexed from zero; at or above this level the answer is read as risky.
RISKY_SCORE = 2.0

ADVICE = {
    "tool_gate": (
        "skip_tool",
        "consider_read",
        "consider_search",
        "consider_shell",
        "consider_browser",
        "ask_human",
    ),
    "skill_gate": ("no_skill", "view_one", "ask_human"),
    "model_route": ("keep_model", "route_nano_or_small"),
    "review_gate": ("show_diff_wait", "ask_human", "apply_advice_only"),
    "decide": ("auto_act", "propose", "escalate", "abstain"),
}

# The arbiter's gate: a bot may act on a pick only when the choice is confident,
# well-separated from the runner-up, and Jev judges the field acceptable. All
# three are required; the thresholds are the starting points to calibrate.
DECIDE_AUTO_ACCEPT = 0.85
DECIDE_MIN_MARGIN = 0.5

_TOOL_FAMILY_ADVICE = {
    "none": "skip_tool",
    "read": "consider_read",
    "search": "consider_search",
    "shell": "consider_shell",
    "browser": "consider_browser",
    "review": "ask_human",
}


class AdviceError(ValueError):
    pass


def _noul(answers: Mapping[str, Any], qid: str, default: float = 0.0) -> float:
    answer = answers.get(qid)
    if not isinstance(answer, Mapping) or answer.get("type") != "noul":
        return default
    value = answer.get("noul")
    return float(value) if isinstance(value, (int, float)) else default


def _choice(answers: Mapping[str, Any], qid: str, default: str | None = None) -> str | None:
    answer = answers.get(qid)
    if not isinstance(answer, Mapping) or answer.get("type") != "choice":
        return default
    value = answer.get("choice")
    return value if isinstance(value, str) else default


def _score(answers: Mapping[str, Any], qid: str, default: float = 0.0) -> float:
    answer = answers.get(qid)
    if not isinstance(answer, Mapping) or answer.get("type") != "score":
        return default
    value = answer.get("score")
    return float(value) if isinstance(value, (int, float)) else default


def advise(pack: str, answers: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``{"pack", "advice", "reasons", "signals"}`` for one answer map."""
    if pack not in ADVICE:
        raise AdviceError(f"unknown pack {pack!r}; known: {', '.join(sorted(ADVICE))}")
    if not isinstance(answers, Mapping) or not answers:
        raise AdviceError("answers must be a non-empty map")

    builder = _BUILDERS[pack]
    advice, reasons, signals = builder(answers)
    if advice not in ADVICE[pack]:
        raise AdviceError(f"{pack} produced unknown advice {advice!r}")
    return {
        "pack": pack,
        "advice": advice,
        "reasons": reasons,
        "signals": signals,
    }


def _tool_gate(answers: Mapping[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    need_tool = _noul(answers, "need_tool")
    side_effect = _noul(answers, "side_effect")
    need_evidence = _noul(answers, "need_new_evidence")
    family = _choice(answers, "tool_family") or "none"
    signals = {
        "need_tool": need_tool,
        "need_new_evidence": need_evidence,
        "side_effect": side_effect,
        "tool_family": family,
    }
    reasons: list[str] = []

    if need_tool <= NEGATIVE:
        reasons.append(f"need_tool {need_tool:.2f} is at or below {NEGATIVE}")
        return "skip_tool", reasons, signals
    if family == "none":
        reasons.append("tool_family is none")
        return "skip_tool", reasons, signals
    if family == "review":
        reasons.append("tool_family is review: stop and ask")
        return "ask_human", reasons, signals

    # A clearly-mutating call is never auto-considered, no matter the family:
    # escalate to a human when the side-effect signal is strong. Read-only
    # lookups (read/search/browser) leave the machine but change nothing, so a
    # high side_effect there is informational, not blocking.
    if side_effect >= STRONG_POSITIVE and family in {"shell"}:
        reasons.append(
            f"side_effect {side_effect:.2f} is at or above {STRONG_POSITIVE}: "
            "the tool mutates, spends, or deploys"
        )
        return "ask_human", reasons, signals

    advice = _TOOL_FAMILY_ADVICE.get(family)
    if advice is None:
        reasons.append(f"unrecognised tool_family {family!r}")
        return "ask_human", reasons, signals

    reasons.append(f"need_tool {need_tool:.2f} and tool_family {family}")
    if side_effect >= POSITIVE:
        reasons.append(
            f"side_effect {side_effect:.2f} is at or above {POSITIVE}: "
            "confirm with the operator before running it"
        )
    if need_evidence <= NEGATIVE and family in {"read", "search", "browser"}:
        reasons.append(
            f"need_new_evidence {need_evidence:.2f} is at or below {NEGATIVE}: "
            "the lookup may be unnecessary"
        )
    return advice, reasons, signals


def _skill_gate(answers: Mapping[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    need_skill = _noul(answers, "need_skill")
    just_talk = _noul(answers, "just_talk")
    action = _choice(answers, "skill_action") or "none"
    signals = {"need_skill": need_skill, "just_talk": just_talk, "skill_action": action}
    reasons: list[str] = []

    if just_talk >= STRONG_POSITIVE:
        reasons.append(f"just_talk {just_talk:.2f} is at or above {STRONG_POSITIVE}")
        return "no_skill", reasons, signals
    if action == "none":
        # Jev said "none", but a strong need_skill overrules it — the choice
        # question is noisier than the noul on borderline procedural tasks.
        if need_skill >= POSITIVE:
            reasons.append(
                f"skill_action is none but need_skill {need_skill:.2f} is at or above "
                f"{POSITIVE}: load the matching skill"
            )
            return "view_one", reasons, signals
        reasons.append("skill_action is none")
        return "no_skill", reasons, signals
    if action == "ask":
        reasons.append("skill_action is ask")
        return "ask_human", reasons, signals
    if need_skill <= NEGATIVE:
        reasons.append(f"need_skill {need_skill:.2f} is at or below {NEGATIVE}")
        return "no_skill", reasons, signals
    reasons.append(f"need_skill {need_skill:.2f} with skill_action view_one")
    return "view_one", reasons, signals


def _model_route(answers: Mapping[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    tier = _choice(answers, "model_tier") or "mid"
    cheap_ok = _noul(answers, "cheap_ok")
    needs_reasoning = _noul(answers, "needs_reasoning")
    context_fat = _noul(answers, "context_fat")
    task_kind = _choice(answers, "task_kind")
    signals = {
        "task_kind": task_kind,
        "model_tier": tier,
        "cheap_ok": cheap_ok,
        "needs_reasoning": needs_reasoning,
        "context_fat": context_fat,
    }
    reasons: list[str] = []

    if tier in {"nano", "small"}:
        reasons.append(f"model_tier {tier}: this shard could run on a cheaper model")
        advice = "route_nano_or_small"
    else:
        reasons.append(f"model_tier {tier}: keep the session model")
        advice = "keep_model"
    if needs_reasoning >= STRONG_POSITIVE and advice == "route_nano_or_small":
        reasons.append(
            f"needs_reasoning {needs_reasoning:.2f} is at or above {STRONG_POSITIVE}: "
            "do not downshift this shard"
        )
        advice = "keep_model"
    if cheap_ok >= POSITIVE and needs_reasoning <= NEGATIVE:
        reasons.append("cheap_ok is high and needs_reasoning is low")
    if context_fat >= POSITIVE:
        reasons.append(f"context_fat {context_fat:.2f}: trim the prompt before sending it")
    return advice, reasons, signals


def _review_gate(answers: Mapping[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    tests_support = _noul(answers, "tests_support")
    safe_to_apply = _noul(answers, "safe_to_apply")
    risk = _score(answers, "risk")
    action = _choice(answers, "action") or "show"
    signals = {
        "tests_support": tests_support,
        "safe_to_apply": safe_to_apply,
        "risk": risk,
        "action": action,
    }
    reasons: list[str] = []

    if action == "apply":
        reasons.append("action apply: advice only, the helper never applies a patch")
        return "apply_advice_only", reasons, signals
    if action == "ask":
        # Jev leaning "ask" is a soft signal; strong supporting signals can
        # overrule it. Only a genuinely risky change still stops for a human.
        if tests_support >= POSITIVE and safe_to_apply >= POSITIVE and risk < RISKY_SCORE:
            reasons.append(
                f"action ask, but tests_support {tests_support:.2f}, "
                f"safe_to_apply {safe_to_apply:.2f}, risk {risk:.2f}: low-risk, "
                "tests green — show the diff and wait"
            )
            return "show_diff_wait", reasons, signals
        reasons.append("action ask")
        return "ask_human", reasons, signals
    if tests_support < POSITIVE:
        reasons.append(f"tests_support {tests_support:.2f} is below {POSITIVE}")
        return "show_diff_wait", reasons, signals
    if safe_to_apply < POSITIVE:
        reasons.append(f"safe_to_apply {safe_to_apply:.2f} is below {POSITIVE}")
        return "show_diff_wait", reasons, signals
    if risk >= RISKY_SCORE:
        reasons.append(f"risk {risk:.2f} is at or above level {RISKY_SCORE:.0f}")
        return "ask_human", reasons, signals
    reasons.append("tests support the change and risk is below the risky level")
    return "show_diff_wait", reasons, signals


def _decide(answers: Mapping[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    """Arbiter: Jev proposes a candidate, the policy decides if a bot may act.

    The pick is read off the choice probabilities, not just the argmax, so a
    coin-flip between two candidates surfaces instead of hiding behind one word.
    """
    from .packs.decide import ESCAPE_ASK, ESCAPE_NONE

    pick_answer = answers.get("pick", {})
    any_good = _noul(answers, "any_good")
    confident = _noul(answers, "confident")

    choice = pick_answer.get("choice") if isinstance(pick_answer, Mapping) else None
    confidence = pick_answer.get("confidence", 0.0) if isinstance(pick_answer, Mapping) else 0.0
    probabilities = pick_answer.get("probabilities", {}) if isinstance(pick_answer, Mapping) else {}

    # Margin: how far the winner leads the runner-up. The whole point of the
    # gate — a 0.51/0.49 pick is a coin flip even when the winner is "confident".
    ordered = sorted(probabilities.values(), reverse=True)
    top = ordered[0] if ordered else 0.0
    runner_up = ordered[1] if len(ordered) > 1 else 0.0
    margin = top - runner_up

    signals = {
        "pick": choice,
        "confidence": confidence,
        "margin": round(margin, 4),
        "any_good": any_good,
        "confident": confident,
        "probabilities": probabilities,
    }
    reasons: list[str] = []

    if choice is None:
        reasons.append("no pick answer")
        return "abstain", reasons, signals
    if choice == ESCAPE_NONE:
        reasons.append("Jev declined: no candidate is acceptable")
        return "abstain", reasons, signals
    if choice == ESCAPE_ASK:
        reasons.append("Jev declined: the evidence or priorities are insufficient")
        return "escalate", reasons, signals
    if any_good < POSITIVE:
        reasons.append(f"any_good {any_good:.2f} is below {POSITIVE}: no candidate is genuinely acceptable")
        return "abstain", reasons, signals
    if confident < POSITIVE:
        reasons.append(f"confident {confident:.2f} is below {POSITIVE}: the field does not separate")
        return "escalate", reasons, signals

    if confidence >= DECIDE_AUTO_ACCEPT and margin >= DECIDE_MIN_MARGIN:
        reasons.append(
            f"confidence {confidence:.2f} and margin {margin:.2f} clear the gate "
            f"({DECIDE_AUTO_ACCEPT}/{DECIDE_MIN_MARGIN}): a bot may act on {choice!r}"
        )
        return "auto_act", reasons, signals

    reasons.append(
        f"confidence {confidence:.2f} or margin {margin:.2f} is below the gate "
        f"({DECIDE_AUTO_ACCEPT}/{DECIDE_MIN_MARGIN}): propose {choice!r}, do not act"
    )
    return "propose", reasons, signals


_BUILDERS = {
    "tool_gate": _tool_gate,
    "skill_gate": _skill_gate,
    "model_route": _model_route,
    "review_gate": _review_gate,
    "decide": _decide,
}
