from .decide import build as DECIDE_BUILD
from .model_route import QUESTIONS as MODEL_ROUTE
from .review_gate import QUESTIONS as REVIEW_GATE
from .skill_gate import QUESTIONS as SKILL_GATE
from .tool_gate import QUESTIONS as TOOL_GATE

PACKS = {
    "tool_gate": TOOL_GATE,
    "model_route": MODEL_ROUTE,
    "review_gate": REVIEW_GATE,
    "skill_gate": SKILL_GATE,
    # decide is built per call from the candidate list; see packs/decide.py
}

__all__ = ["PACKS", "TOOL_GATE", "MODEL_ROUTE", "REVIEW_GATE", "SKILL_GATE", "DECIDE_BUILD"]
