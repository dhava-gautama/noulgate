from ..schemas import choice, noul, score

QUESTIONS = {
    "tests_support": noul(
        "The test summary supports shipping this change",
        true="Relevant tests ran and passed, or the change is covered by existing green tests",
        false="Tests failed, were skipped, or do not cover the change",
    ),
    "safe_to_apply": noul(
        "Applying this change without further human review is acceptable",
        true="Small, reversible, non-security, tests support it",
        false="Touches auth, data, deploy, secrets, or is poorly tested",
    ),
    "risk": score(
        "How risky is applying this diff without a human",
        [
            "No production impact, reversible, tests green",
            "Local-only change, tests incomplete",
            "Touches auth, data, or deploy path",
            "Irreversible or security-sensitive",
        ],
    ),
    "action": choice(
        "What should the operator do with this diff",
        {
            "show": "Print the diff and wait",
            "ask": "Ask a clarifying question before any apply",
            "apply": "Advice only — helper will still refuse to apply",
        },
    ),
}
