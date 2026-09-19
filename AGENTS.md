# Agent notes

You are the coding agent. Your chat model does not change.

Before a costly tool call or a long generation, you may run:

```
python -m jev decide --pack tool_gate --state-file /tmp/jev-state.json
```

Default is dry-run (offline fixture). Treat stdout JSON as advice, and read
`reasons` before `advice`. Never apply a patch or fire a mutating tool
because Jev returned a high noul, `consider_*`, or `apply_advice_only`.

Do not install `typesafe-ai/skills` unless the human says which route to use.
Do not read or print `EXPERIENTIAL_API_KEY`.
Do not POST live without an explicit yes plus `JEV_ALLOW_LIVE=1`.
