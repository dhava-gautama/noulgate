# Blueprint

What noulgate is, what it refuses to do, and why. Read this before you change
anything — the design is a set of deliberate absences, and each one is load-bearing.

## When to reach for it

Jev earns its place when three things are true at once: you already know the set
of possible answers, you make the same decision repeatedly, and you can act on a
confidence score. That describes almost every routing, gating, and screening step
inside an agent loop — and almost nothing else. If you need prose, reach for a
chat model; noulgate is for the decision steps around it.

## Shape

```
jev/
  schemas.py     question builders + the gateway's limits, in one place
  packs/         the question packs: tool_gate, skill_gate, model_route, review_gate
  packs/decide.py  the arbiter: build pick-one-of-N questions from candidates
  compress.py    build a small state blob instead of dumping a repo
  providers.py   where a live call goes: direct gateway or OpenRouter Decisions
  client.py      one POST; no retries, no streaming, no chat
  dryrun.py      offline fixture transport, schema-shaped answers, no network
  policies.py    answers -> one advice word, with the reasons spelled out
  calibrate.py   score the policy thresholds against real answers
  __main__.py    the CLI
skills/noulgate/SKILL.md   what the harness loads (advisory)
scripts/install-*.sh                  copy that skill into a harness (hermes,
                                      kimi, claude, codex, pi, omp, generic)
scripts/jev-gate-hook.py              blocking hook: exit-2 contract (kimi-code,
                                      Claude Code, Codex, Hermes)
scripts/jev-gate-hook.ts              blocking extension: tool_call host (Pi, OMP)
```

Install into your harness: see `docs/INSTALL.md`.

## Advisory vs enforced

The skill teaches the agent to gate; the hooks make the gate mandatory for shell
commands. Both run the same two layers: a narrow denylist of destructive commands
(`rm -rf`, `dd` to a device, `mkfs`, force-push, `drop database`) blocks with no
model call, and other mutating commands get a live Jev read as advisory. Reads,
non-mutating commands, and any hook error fail open — a gate must never stop a
safe operation or break the session. The hook is lightweight interception, not
the sole security barrier; high-risk operations still need permission approvals.

## Two providers, one contract

A live call goes to one of three places, all speaking the same
`{model, state, questions}` → `{answers, usage}` contract:

| Provider | Endpoint | Key env | Model slug |
|---|---|---|---|
| Gateway (Experiential) | `POST https://api.experientiallabs.ai/v1/systemone` | `EXPERIENTIAL_API_KEY` / `EXPLABS_API_KEY` / kimi `providers.explabs` | `jev-latest` |
| TypeSafe direct | `POST https://api.typesafe.ai/v1/systemone` | `TYPESAFE_API_KEY` | `jev-latest` |
| OpenRouter | `POST https://openrouter.ai/api/alpha/decisions` | `OPENROUTER_API_KEY` | `typesafe/jev-1.13` |

The gateway is a managed proxy in front of TypeSafe; TypeSafe direct is the
official API with a console key. `providers.py` picks: a `TYPESAFE_API_KEY` goes
direct (no proxy in the middle), a gateway key uses Experiential, OpenRouter is
the fallback, and `JEV_PROVIDER` (or `--provider`) forces one. OpenRouter has no
`latest`
alias, so the helper maps `jev-latest` to the pinned `typesafe/jev-1.13` and
lets `JEV_MODEL` override. The endpoint is alpha and adds a hop; direct is the
recommended default when both keys exist.

## The one design rule

Jev returns probabilities. The agent needs a decision. `policies.py` is the only
place that crosses that line, so the crossing is auditable in one file.

Every advice word is deliberately weak — `consider_*`, `show_diff_wait`,
`apply_advice_only` — because the output is a *judgement about the situation*,
not permission to act. `apply_advice_only` exists so that "Jev said apply" can
never be quoted as authorisation: the helper will not apply anything, ever.

## Why not the official SDK

`typesafe-sdk` is a fine chat-adjacent client: retries, tenacity, msgspec, a
`models` resource. None of that is wanted here.

- **No retries.** A retry on a charged POST is a silent double spend. If the
  call fails, the agent decides whether to ask again.
- **No key handling beyond one env var.** `EXPERIENTIAL_API_KEY` is read, put in
  a header, and never logged, echoed, or written to disk. `redacted_headers()`
  exists so that debugging output cannot leak it.
- **No chat facade.** `/v1/chat/completions` is a different product. This helper
  speaks only `/v1/systemone`, only `choice`/`noul`/`score`.
- **No dependency.** `urllib` from the standard library, so the helper runs
  anywhere Python 3.10+ runs, including a machine where installing packages is
  itself the thing being gated.

## The three-way live gate

A real POST is the only thing here that costs money, so it needs three
independent yeses:

| Gate | Set by | Purpose |
|---|---|---|
| `--live` | the command line | the caller means it, this time |
| `JEV_ALLOW_LIVE=1` | the operator's environment | the machine is allowed to spend |
| a key | the operator's environment or kimi config | there is a key to spend with |

The key is whichever provider resolves — a direct-gateway env var or kimi-config
`explabs` key, or `OPENROUTER_API_KEY`. Any one gate missing is a refusal with a
distinct message. Nothing in the code sets these; only a human does. `.gitignore`
lists `JEV_ALLOW_LIVE` and `.env*` so an accidental commit cannot carry the key.

## The dry-run

`dryrun.py` answers the pack from the state text alone — keyword families,
thresholds, the same wire shapes the gateway returns. It is a *shape check*, not
a prediction: the CLI stamps every dry-run with
`"notice": "fixture answers, not a Jev call"` so nobody mistakes one for a
verdict. Its job is to keep the whole path exercised without a key, and to make
the tests hermetic.

## Packs

Each gate pack is a small map of questions whose names `policies.py` knows.
Adding a question means adding it to the pack, to `policies.py`, and to `ADVICE`;
the test suite asserts every pack's advice word is declared, so a mismatch fails
loudly rather than silently falling back.

| Pack | Answers | Advice words |
|---|---|---|
| `tool_gate` | is a tool needed, what family, does it mutate | `skip_tool`, `consider_*`, `ask_human` |
| `skill_gate` | does this need a written procedure | `no_skill`, `view_one`, `ask_human` |
| `model_route` | what kind of shard, how big a model | `keep_model`, `route_nano_or_small` |
| `review_gate` | do tests support this, how risky | `show_diff_wait`, `ask_human`, `apply_advice_only` |

## The arbiter

`decide` is the one pack that isn't a fixed map: the candidates change per
decision, so `packs/decide.py:build(candidates)` makes the questions at call
time — a `choice` over the candidates plus two escape hatches, a `noul` for
"is any candidate genuinely acceptable," and a `noul` for "is the winner clearly
separated."

The policy reads the pick off the choice *probabilities*, not the argmax, so a
coin flip surfaces instead of hiding. A bot may act (`auto_act`) only when the
winner's confidence ≥ `DECIDE_AUTO_ACCEPT` (0.85), its margin over the runner-up
≥ `DECIDE_MIN_MARGIN` (0.5), and Jev judges the field acceptable and the pick
separated. Anything else is `propose`, `escalate`, or `abstain` — the bot stops
or asks. Even `auto_act` is a proposal: what the bot does with it is the caller's
policy, never the helper's.

## Known limits

- The gateway caps a request at 32 questions, 64 choice options, and 2–10 score
  levels. `schemas.py` enforces those before a POST, because a 422 costs a round
  trip and a retry temptation.
- `policies.py` thresholds are calibrated against the recorded batch in
  `fixtures/calibration.json` — run `python -m jev.calibrate --save …` to add
  real cases, `--replay` to re-score offline. A test replays the fixture and
  fails on any regression, so a threshold change that breaks a known case is
  caught in CI.
- The dry-run's keyword lists are English-only and crude. It is a fixture; its
  output is `fixture_advice`, never a decision.
