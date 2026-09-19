from ..schemas import choice, noul

QUESTIONS = {
    "task_kind": choice(
        "What kind of work is this shard",
        {
            "chat": "Short answer or explanation, no tools required",
            "lookup": "Find a fact in files or on the web",
            "edit": "Write or modify code",
            "plan": "Break a task into steps without executing them",
            "review": "Judge an existing diff or design",
            "research": "Multi-source investigation",
        },
    ),
    "cheap_ok": noul(
        "A small cheap model can complete this shard without likely rework",
        true="Narrow, well-specified, low-ambiguity work",
        false="Ambiguous, high-stakes, or long-horizon synthesis",
    ),
    "needs_reasoning": noul(
        "The shard needs multi-step reasoning or careful code synthesis",
        true="Architecture, subtle bug, security, or multi-file consistency",
        false="Boilerplate, formatting, lookup, or mechanical transform",
    ),
    "model_tier": choice(
        "Which capability tier matches the shard",
        {
            "nano": "Classification, routing, short lookup",
            "small": "Routine code edits, summaries, cheap research loops",
            "mid": "Standard feature work the session model already handles",
            "frontier": "Hard reasoning, novel design, or high-cost failure",
        },
    ),
    "context_fat": noul(
        "The planned prompt is larger than the task needs",
        true="Whole files or long history could be replaced by a diff or excerpt",
        false="The planned context is already tight",
    ),
}
