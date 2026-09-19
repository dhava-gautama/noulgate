# noulgate

**Ask before your agent spends.** noulgate is a gate for an AI agent's expensive
steps — the web search, the shell command, the big skill load, the apply — powered
by [TypeSafe's Jev](https://typesafe.ai), a System One model that answers
structured `choice` / `noul` / `score` questions instead of generating text.

noulgate turns Jev's probabilities into **one advice word with its reasons**, so
your agent can decide *whether* to act before it decides *how*.

> "Noul" is Jev's own word for a yes/no probability. This is the gate that asks
> before it acts.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![No dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)]()

---

## The problem

Your agent is about to do something costly. Right now it has two options: guess,
or burn a frontier model call on a yes/no it could have gotten for a fraction of
the price and latency. Neither is great.

```
agent:  "should I search the web for this, or do I already know?"
        → guesses, or spends 2 s and a big-model call on a routing decision
```

## The gate

```
agent:  → noulgate → Jev (System One)
jev:    {"need_tool": 0.85, "tool_family": "search", "side_effect": 0.2}
noulgate → advice: "consider_search"
agent:  now it searches — because the gate said the tool is justified
```

One call. ~150 ms. A fraction of a cent. The agent acts on the *advice*, not on a
guess.

## Get a decision in 30 seconds (no key, no spend)

```bash
git clone https://github.com/dhava-gautama/noulgate.git
cd noulgate
python -m jev decide --pack tool_gate --goal "search the web for the current BMKG forecast" --tool web_search
```

```json
{
  "mode": "dry-run",
  "advice": null,
  "fixture_advice": "consider_search",
  "reasons": ["need_tool 0.85 and tool_family search"],
  "signals": { "need_tool": 0.85, "need_new_evidence": 0.8, "side_effect": 0.2, "tool_family": "search" }
}
```

Dry-run is the default and needs nothing: `dryrun.py` answers the pack from the
state text, offline. It returns `"advice": null` on purpose and puts the keyword
heuristic's guess in `fixture_advice` — that word is a **shape check, not a
decision**, so a dry-run can never be misread as a verdict. Run `--live` for a
real answer.

## Ask Jev for real

```bash
JEV_ALLOW_LIVE=1 python -m jev decide --pack skill_gate --state-text "user: hey, how are you" --live
```

```json
{ "mode": "live", "provider": "experiential", "advice": "no_skill",
  "reasons": ["just_talk 0.95 is at or above 0.7"],
  "usage": { "input_tokens": 466, "output_tokens": 75, "cost": 0.0 } }
```

A live POST needs three independent yeses, so an accident can't spend money:

| Gate | Set by | Purpose |
|---|---|---|
| `--live` | the command line | the caller means it, this time |
| `JEV_ALLOW_LIVE=1` | the environment | this machine is allowed to spend |
| a key | the environment or your config | there's a key to spend with |

Any one missing is a refusal with a distinct message. Nothing in the code sets
them; only you do.

## When Jev can't be reached

If the gateway is unreachable or the key is rejected (401/403, timeout, DNS),
a live call **fails open**: it returns `{"mode": "pass", "advice": "pass"}` with
exit 0, so the caller keeps working instead of halting on a gate that's down.
The output says so (`"notice": "…this is a pass-through, not a decision"`), and
the `status` carries the HTTP code when there is one. A gate must never become a
single point of failure for the work it's gating.

## Three providers, one contract

Jev is TypeSafe's model. noulgate speaks one contract — `{model, state, questions}`
→ `{answers, usage}` — to three endpoints:

| Provider | Endpoint | Key | Model slug |
|---|---|---|---|
| **Gateway** (Experiential) | `POST api.experientiallabs.ai/v1/systemone` | `EXPERIENTIAL_API_KEY` · `EXPLABS_API_KEY` | `jev-latest` |
| **TypeSafe direct** | `POST api.typesafe.ai/v1/systemone` | `TYPESAFE_API_KEY` | `jev-latest` |
| **OpenRouter** | `POST openrouter.ai/api/alpha/decisions` | `OPENROUTER_API_KEY` | `typesafe/jev-1.13` |

The **gateway** is a managed proxy in front of TypeSafe (the response carries
`"provider": "typesafe"`); **TypeSafe direct** hits the official API with a
console key from `console.typesafe.ai/settings/keys`. A TypeSafe key goes direct
(no gateway in the middle); a gateway key uses Experiential; OpenRouter is the
fallback. Force one with `--provider experiential|typesafe|openrouter` (or
`JEV_PROVIDER`). The gateway key is also read from `providers.explabs.api_key` in
`~/.kimi-code/config.toml` if you use kimi-code (skip that with
`--no-kimi-config`). OpenRouter has no `latest` alias, so `jev-latest` maps to
the pinned `typesafe/jev-1.13` (`JEV_MODEL` overrides); point at another gateway
entirely with `JEV_URL`.

*OpenRouter status: implemented and unit-tested; the Decisions endpoint is alpha,
so verify against a live key before you depend on it.*

## Use it from your harness

One command installs the `noulgate` skill into whatever loads skills:

| Harness | Command | Lands at |
|---|---|---|
| [Hermes](https://github.com/typesafe-ai/hermes) | `bash scripts/install-hermes.sh` | `~/.hermes/skills/software-development/noulgate/` |
| kimi-code | `bash scripts/install-kimi.sh` | `~/.agents/skills/noulgate/` |
| Claude Code | `bash scripts/install-claude.sh` | `~/.claude/skills/noulgate/` + a `/jev` command |
| Codex | `bash scripts/install-codex.sh` | `~/.codex/skills/` + an `AGENTS.md` gate block |
| Pi | `bash scripts/install-pi.sh` | `~/.pi/agent/skills/noulgate/` |
| Oh My Pi | `bash scripts/install-omp.sh` | `~/.omp/agent/skills/noulgate/` |
| any other | `bash scripts/install-skill.sh <skills-dir>` | `<skills-dir>/noulgate/` |

Then tell your agent, once: *"use noulgate before tool calls and
skill loads."* The skill teaches it the two-stage pattern — gate first, load at
most one skill, never act on a Jev word alone. Per-harness detail:
[`docs/INSTALL.md`](docs/INSTALL.md).

## Enforce it (hooks)

The skill is advisory — the agent chooses to call it. To make the gate
*mandatory* for shell commands, wire the blocking hook `scripts/jev-gate-hook.py`
into your harness. It uses the shared exit-2-blocks contract, so the same script
works in kimi-code, Claude Code, Codex, Hermes, and Cursor; a TypeScript
extension (`scripts/jev-gate-hook.ts`) covers Pi and Oh My Pi. Per-harness
config: [`docs/INSTALL.md`](docs/INSTALL.md).

kimi-code, in `~/.kimi-code/config.toml`:

```toml
[[hooks]]
event = "PreToolUse"
matcher = "Bash"
command = "python3 /path/to/noulgate/scripts/jev-gate-hook.py"
timeout = 20
```

Two layers, on purpose:

- **Destructive commands block** (exit 2) on a narrow denylist — `rm -rf`, `dd`
  to a device, `mkfs`, force-push, `drop database` — no model call. These are the
  only commands a hook should ever stop.
- **Other mutating commands** (`pip install`, `git push`, `curl -X POST`, …) get a
  live Jev read appended to the context as an advisory line. The agent sees it;
  the command runs.

Reads, non-mutating commands, and any hook error **fail open** — a hook never
stops a safe operation or breaks the session. The advisory layer needs
`JEV_ALLOW_LIVE=1`; without it the hook only enforces the denylist. kimi-code's
docs are explicit that hooks are a lightweight interception, not the sole
security barrier — for genuinely high-risk operations, keep permission approvals
on.

## The four gates

Each gate pack asks a handful of questions and returns one advice word with reasons:

| Pack | When to call it | Asks | Can advise |
|---|---|---|---|
| `tool_gate` | before a tool call | is a tool needed, which family, does it mutate | `skip_tool` · `consider_read` · `consider_search` · `consider_shell` · `consider_browser` · `ask_human` |
| `skill_gate` | before loading a skill | does this need a written procedure | `no_skill` · `view_one` · `ask_human` |
| `model_route` | before a long generation | what kind of shard, how big a model | `keep_model` · `route_nano_or_small` |
| `review_gate` | after a diff + test tail | do tests support it, how risky | `show_diff_wait` · `ask_human` · `apply_advice_only` |

`consider_*` means the tool family is justified, not that the call is.
`apply_advice_only` means exactly that — **noulgate never applies a patch, fires
a mutating tool, or swaps your chat model, no matter what Jev returns.**

## The arbiter: let a bot pick one of N

The gates answer "should I do this?" The `decide` pack answers "which of these?"
— for a bot that proposes several options and needs the best one, automatically:

```bash
python -m jev decide --pack decide --candidates "poll,push,queue" \
  --goal "Deliver status updates. Evidence: polling hits the existing endpoint within 30s; managed push is 1s but adds a paid vendor. Priorities: no new paid service; 30s is fine." \
  --live
```

```json
{ "advice": "auto_act",
  "signals": { "pick": "poll", "confidence": 0.99, "margin": 1.0 } }
```

Jev *proposes*; a policy in the code *disposes*. A bot may act only when the pick
is confident, well-separated from the runner-up, and Jev judges the field
acceptable — otherwise it escalates or abstains. Four outcomes:

| Advice | Meaning | A bot should |
|---|---|---|
| `auto_act` | confident + margin ≥ gate + field acceptable | act on the pick |
| `propose` | a winner, but below the confidence/margin gate | hand it to a human or a bigger model |
| `escalate` | the field doesn't separate, or Jev asked for a human | stop and ask |
| `abstain` | Jev declined, or no candidate is acceptable | do nothing |

The pick is read off the choice **probabilities**, not the argmax, so a 0.51/0.49
coin flip surfaces as `escalate` instead of hiding behind a winner. Two escape
hatches — `none` and `ask_human` — let Jev decline rather than pick the least
bad option; `--no-escapes` removes them for a closed-world pick. The gate
(`confidence ≥ 0.85`, `margin ≥ 0.5`) is a starting point, calibrated against the
recorded batch in `fixtures/calibration.json` — add your own cases with
`python -m jev.calibrate --save`.

**Even `auto_act` is a proposal, not a command.** What your bot does with it is
your policy, in your code — noulgate never executes the pick.

## Why not the official SDK

[`typesafe-sdk`](https://pypi.org/project/typesafe-sdk/) is a fine client —
retries, msgspec, a models resource. None of that is wanted in a gate:

- **No retries.** A retry on a charged POST is a silent double spend.
- **No key handling beyond lookup.** The key is found, put in a header, and never
  logged, echoed, or written to disk.
- **No chat facade.** Only the decision endpoints, only `choice`/`noul`/`score`.
- **No dependency.** `urllib` from the standard library; runs anywhere Python
  3.10+ runs.

## Docs

- [`docs/INSTALL.md`](docs/INSTALL.md) — install into Hermes, kimi-code, Claude Code, Codex, Pi, Oh My Pi, or anything else
- [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) — the design, the live gate, the limits
- [`docs/HERMES.md`](docs/HERMES.md) — wiring for Hermes
- [`skills/noulgate/SKILL.md`](skills/noulgate/SKILL.md) — what the harness loads

## License

[MIT](LICENSE)
