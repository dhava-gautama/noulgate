---
name: noulgate
description: Gate tool and skill loads with TypeSafe Jev (System One). Not a chat model.
version: 0.2.0
license: MIT
platforms: [linux, macos]
metadata:
  tags: [routing, tokens, typesafe, jev, tools]
  category: software-development
  requires_tools: [terminal]
required_environment_variables:
  - EXPERIENTIAL_API_KEY
---

# noulgate

Jev is a System One judge. It returns `choice` / `noul` / `score`. It does not chat.

Keep the current chat model. Call Jev before expensive work.

Helper root (this repo, not a vendor SDK): `noulgate/` next to this skill,
or set `JEV_HELPER_ROOT`.

## When to use

- Before `web_search`, browser, mutating shell, or loading a large skill
- Before a long generation you could downshift
- After a diff + test tail, before any apply

Skip Jev for greetings and one-line answers you already know.

## Invoke

Write compact state. Do not dump the repo. `--state-text` is enough for a short
turn; `--goal` builds the blob for you and clips the diff.

```bash
ROOT="${JEV_HELPER_ROOT:-.}"
python -m jev decide --pack skill_gate --state-file /tmp/jev-state.json
python -m jev decide --pack tool_gate --state-file /tmp/jev-state.json
python -m jev decide --pack model_route --state-file /tmp/jev-state.json
python -m jev decide --pack review_gate --state-file /tmp/jev-state.json
```

Run from `$ROOT` so `python -m jev` resolves. Default is dry-run: fixture
answers, no network, no key. A dry-run returns `"advice": null` and puts the
heuristic guess in `fixture_advice` — that word is a **shape check, not a
decision**. Never act on `fixture_advice`; run `--live` for a real answer.
`python -m jev packs` lists the packs, their questions, and the advice words
each can return.

Live POST is blocked until all three are set: `--live`, `JEV_ALLOW_LIVE=1`, and
an API key. The helper picks a provider and finds the key itself:
- gateway (default): `EXPERIENTIAL_API_KEY`, `EXPLABS_API_KEY`, or
  `providers.explabs` in `~/.kimi-code/config.toml` (skip with `--no-kimi-config`)
- TypeSafe direct (`--provider typesafe`): `TYPESAFE_API_KEY` → api.typesafe.ai
- OpenRouter (`--provider openrouter`): `OPENROUTER_API_KEY` → the Decisions API

Never print the key. Never paste it into a prompt.

Live targets: `POST https://api.experientiallabs.ai/v1/systemone` (gateway),
`POST https://api.typesafe.ai/v1/systemone` (TypeSafe direct), or
`POST https://openrouter.ai/api/alpha/decisions` (OpenRouter).
Model: `jev-latest` direct, `typesafe/jev-1.13` on OpenRouter.

## After stdout JSON

Show `advice`, `reasons`, `answers`, and `usage`. `reasons` says which signals
produced the word — read it, do not just read the word. In dry-run mode `advice`
is `null` on purpose; only act on a live `advice`.

- `skip_tool` / `no_skill` — stay in chat, load nothing
- `consider_read` / `consider_search` / `consider_shell` / `consider_browser` — the tool family is justified, not the call itself
- `view_one` — load one matching skill, at most
- `ask_human` — ask the operator; do not guess
- `keep_model` / `route_nano_or_small` — `route_*` is for a shard only; never change the session model
- `show_diff_wait` / `apply_advice_only` — print the diff and wait; `apply_advice_only` means exactly that, and the helper applies nothing

A `side_effect` signal at or above 0.5 means the tool mutates, spends, or leaves
the machine: confirm with the operator even when the family advice says
`consider_*`.

## The arbiter (decide pack)

When the operator hands you several options and wants the best one, use
`--pack decide --candidates "a,b,c"` with the evidence and priorities in `--goal`.
This is for a bot that proposes N options and acts on the pick.

- `auto_act` — confident, well-separated, field acceptable. The pick may be acted on *by the caller's own policy* — noulgate never executes it.
- `propose` — a winner, but below the confidence/margin gate. Hand to a human or a bigger model.
- `escalate` — the field doesn't separate, or Jev asked for a human. Stop and ask.
- `abstain` — Jev declined, or no candidate is acceptable. Do nothing.

Read `signals.pick`, `signals.confidence`, and `signals.margin` — a thin margin
on a confident winner is still a coin flip. Never auto-run a mutating action
because `decide` returned `auto_act`; the word is a proposal, and acting on it is
the operator's policy, not yours.

## When Jev can't be reached

A live call that can't reach Jev (unreachable host, rejected/exhausted key,
timeout) **fails open**: the CLI returns `{"mode": "pass", "advice": "pass"}` and
the hook allows the command. `advice: pass` is not a verdict — it means "the gate
was down, so you're on your own." Decide from your own judgment, and mention the
pass to the operator if the step was risky.

No retries. No Idempotency-Key. No `/v1/chat/completions` for Jev.

## Do not

- Treat any advice word as permission to mutate. The helper never applies a patch.
- Install `typesafe-ai/skills` unless the operator picks that route
- Call `api.typesafe.ai` or request a TypeSafe key
- Auto-merge or auto-run a mutating tool from a Jev choice
- Print or commit the API key
