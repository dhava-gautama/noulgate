from ..schemas import choice, noul

QUESTIONS = {
    "need_tool": noul(
        "A tool call is necessary to complete this turn correctly",
        true="Current context is insufficient; a tool would add new evidence or perform a required action",
        false="The agent can answer, refuse, or plan without calling a tool",
    ),
    "need_new_evidence": noul(
        "The agent lacks a fact that a tool would retrieve and cannot honestly guess",
        true="A missing file, URL, command output, or external fact is required",
        false="The needed facts are already in the state or are not required",
    ),
    "side_effect": noul(
        "The proposed tool can change files, hit the network, or spend money",
        true="Write, apply_patch, shell mutation, paid API, or deploy",
        false="Read-only inspection of existing local context",
    ),
    "tool_family": choice(
        "Which tool family is actually required",
        {
            "none": "Chat model can finish from current context",
            "read": "Read local workspace files already on disk",
            "search": "Web or repo search for unknown facts",
            "shell": "Run a command that inspects or changes the machine",
            "browser": "Load or interact with a live page",
            "review": "Stop and ask a human",
        },
    ),
}
