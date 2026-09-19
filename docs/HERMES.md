# Hermes wiring

Hermes already does progressive skill load:

1. `skills_list()` — names + descriptions
2. `skill_view(name)` — full SKILL.md
3. `skill_view(name, file)` — references

noulgate sits in front of step 2 so Hermes doesn't `skill_view` a hundred skills'
worth of bodies to find the one it needs.

## Install

```bash
cd /path/to/noulgate
bash scripts/install-hermes.sh
```

That copies `skills/noulgate/SKILL.md` to
`~/.hermes/skills/software-development/noulgate/`. Start a new session
(`hermes` or `/reset`), then ask:

> use noulgate before tool calls and skill_view

Or slash-invoke `/noulgate` if your build exposes installed skills that way.

## Session model stays put

`hermes model` is unchanged. `model_route` only advises a cheaper *shard* if you
have one — never swap the live chat model to `jev-latest`; Jev can't chat.

## First run

```bash
cd /path/to/noulgate
python -m jev decide --pack skill_gate --state-text "user: hey, how are you"
```

That's a fixture — offline, no key. A live call needs a key (see the README's
"Two providers" section), `JEV_ALLOW_LIVE=1`, and `--live`.
