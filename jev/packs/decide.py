"""The arbiter pack: pick the best of N candidates, with escape hatches.

The candidates are passed at call time (they change per decision), so the pack
is a builder, not a fixed map. ``build(candidates)`` returns the questions for
``JevClient.decide``; the policy in ``policies.py`` reads the answers back.
"""

from __future__ import annotations

from ..schemas import SchemaError, choice, noul

# Outcomes that are not a candidate. ``none`` and ``ask_human`` let Jev decline
# to pick; the policy turns that into "do nothing" or "escalate", never a guess.
ESCAPE_NONE = "none"
ESCAPE_ASK = "ask_human"
ESCAPES = (ESCAPE_NONE, ESCAPE_ASK)

MAX_CANDIDATES = 6  # a bounded decision; more than this is a ranking, not a pick


def build(candidates: list[str], *, escapes: bool = True) -> dict:
    """Build the decide questions for a concrete candidate list.

    Candidates are short ids (e.g. "poll", "push"); the goal carries the
    evidence and priorities. ``escapes=False`` is a closed-world pick with no
    way out — use it only when every candidate is genuinely acceptable.
    """
    if not candidates:
        raise SchemaError("decide needs at least one candidate")
    if len(candidates) > MAX_CANDIDATES:
        raise SchemaError(f"decide is bounded: at most {MAX_CANDIDATES} candidates")
    if len(set(candidates)) != len(candidates):
        raise SchemaError("decide candidates must be unique")

    options = {c: f"choose {c}" for c in candidates}
    if escapes:
        options[ESCAPE_NONE] = "no candidate is acceptable given the evidence and priorities"
        options[ESCAPE_ASK] = "the evidence or priorities are insufficient; a human should decide"

    return {
        "pick": choice(
            "Which candidate best satisfies the evidence and priorities",
            options,
        ),
        "any_good": noul(
            "At least one candidate is genuinely acceptable, not merely the least bad",
            true="A candidate exists that meets the stated priorities without a serious downside",
            false="Every candidate has a disqualifying downside or the evidence is too thin to pick",
        ),
        "confident": noul(
            "The winning candidate is clearly better than the runner-up, not a coin flip",
            true="The pick is well-separated from the alternatives on the stated priorities",
            false="Two or more candidates are nearly tied, or the evidence does not separate them",
        ),
    }


__all__ = ["build", "ESCAPES", "ESCAPE_NONE", "ESCAPE_ASK", "MAX_CANDIDATES"]
