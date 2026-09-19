from ..schemas import choice, noul

QUESTIONS = {
    "need_skill": noul(
        "This turn needs a specialized skill loaded via skill_view",
        true="The task matches a written procedure the agent should follow instead of improvising",
        false="The agent can talk, answer, or use ordinary tools without loading a skill",
    ),
    "just_talk": noul(
        "The user only wants conversation or a short answer from current context",
        true="No procedure, no repo work, no external lookup required",
        false="The turn requires action, lookup, or a multi-step workflow",
    ),
    "skill_action": choice(
        "What should Hermes do about skills on this turn",
        {
            "none": "Do not call skill_view",
            "view_one": "Load exactly one matching skill",
            "ask": "Ask the operator which skill, if any",
        },
    ),
}
