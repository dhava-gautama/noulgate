"""CLI: ``python -m jev decide --pack tool_gate --state-file …``.

Dry-run by default. A live POST needs all three of ``--live``,
``JEV_ALLOW_LIVE=1``, and ``EXPERIENTIAL_API_KEY``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import compress, dryrun, schemas
from .client import JevClient, JevConfig, JevConfigError, JevTransportError
from .packs import PACKS
from .policies import ADVICE, AdviceError, advise

LIVE_ENV = "JEV_ALLOW_LIVE"
EXIT_USAGE = 2
EXIT_TRANSPORT = 3


def _fail(message: str, code: int) -> None:
    print(f"jev: {message}", file=sys.stderr)
    raise SystemExit(code)


def _read_state(args: argparse.Namespace) -> Any:
    if args.state_text is not None:
        return args.state_text
    if args.state_file is not None:
        with open(args.state_file, encoding="utf-8") as handle:
            return json.load(handle)
    if args.goal is not None:
        diff = None
        if args.diff_file is not None:
            with open(args.diff_file, encoding="utf-8") as handle:
                diff = handle.read()
        return compress.compress_state(
            goal=args.goal,
            intended_tool=args.tool,
            diff=diff,
            test_summary=args.tests,
            session_model=args.session_model,
        )
    _fail("provide --state-file, --state-text, or --goal (see --help for examples)", EXIT_USAGE)


def cmd_packs(_args: argparse.Namespace) -> int:
    listing = {
        name: sorted(questions) for name, questions in sorted(PACKS.items())
    }
    print(json.dumps({"packs": listing, "advice": ADVICE}, indent=2, sort_keys=True))
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    if args.pack == "decide":
        from .packs.decide import build

        candidates = [c.strip() for c in (args.candidates or "").split(",") if c.strip()]
        if not candidates:
            _fail("--pack decide needs --candidates a,b,c", EXIT_USAGE)
        questions = build(candidates, escapes=not args.no_escapes)
    else:
        questions = PACKS[args.pack]
    state = _read_state(args)

    model = args.model or os.environ.get("JEV_MODEL", schemas.DEFAULT_MODEL)
    config = JevConfig(
        url=os.environ.get("JEV_URL", schemas.GATEWAY_URL),
        model=model,
    )

    provider = None
    if args.live:
        if os.environ.get(LIVE_ENV, "").strip() != "1":
            _fail(
                f"--live needs {LIVE_ENV}=1 in this environment. "
                "The operator sets it; the helper never sets it for you.",
                EXIT_USAGE,
            )
        from . import providers

        if args.provider:
            os.environ[providers.PROVIDER_ENV] = args.provider
        try:
            provider = providers.resolve_provider(model, use_kimi_config=not args.no_kimi_config)
        except JevConfigError as exc:
            _fail(str(exc), EXIT_USAGE)
        assert provider is not None
        print(f"jev: live via {provider.name} ({provider.key_source}), model {provider.model}", file=sys.stderr)
        client = JevClient(config=config, live=True, require_auth=True)
        mode = "live"
    else:
        client = JevClient(config=config, transport=dryrun.make_transport(state, questions), live=True, require_auth=False)
        mode = "dry-run"

    try:
        response = client.decide(state, questions, model=model, provider=provider)
    except (JevConfigError, JevTransportError) as exc:
        # Fail open: an unreachable gateway or an exhausted/invalid key must not
        # halt the caller. Emit a pass-through advice the bot can act on, and a
        # distinct mode so nothing mistakes it for a real verdict.
        status = getattr(exc, "status", None)
        out = {
            "mode": "pass",
            "pack": args.pack,
            "advice": "pass",
            "reasons": [f"Jev unreachable ({exc}); passing without a gate"],
            "signals": {},
            "answers": {},
            "usage": {},
            "notice": "Jev could not be reached or the key was rejected; this is a pass-through, not a decision",
        }
        if provider is not None:
            out["provider"] = provider.name
        if status is not None:
            out["status"] = status
        print(json.dumps(out, indent=None if args.compact else 2, sort_keys=args.compact))
        return 0

    answers = response.get("answers", {})
    try:
        advice = advise(args.pack, answers)
    except AdviceError as exc:
        print(json.dumps({"error": str(exc), "mode": mode}, indent=2), file=sys.stderr)
        return EXIT_TRANSPORT

    out = {
        "mode": mode,
        "model": response.get("model", model),
        "pack": args.pack,
        "advice": advice["advice"],
        "reasons": advice["reasons"],
        "signals": advice["signals"],
        "answers": answers,
        "usage": response.get("usage", {}),
    }
    if provider is not None:
        out["provider"] = provider.name
    if mode == "dry-run":
        out["advice"] = None
        out["fixture_advice"] = advice["advice"]
        out["notice"] = (
            "fixture answers, not a Jev call. 'fixture_advice' is a shape check "
            "from keyword heuristics — it is NOT a decision. Run with --live for "
            "a real answer."
        )
    print(json.dumps(out, indent=None if args.compact else 2, sort_keys=args.compact))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m jev",
        description="Ask Jev (System One) for one advice word before costly work. Advice only.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    decide = sub.add_parser("decide", help="ask one question pack about a state blob")
    decide.add_argument("--pack", required=True, choices=sorted(PACKS) + ["decide"])
    decide.add_argument("--state-file", help="JSON state file, e.g. fixtures/sample_state.json")
    decide.add_argument("--state-text", help="state as a plain string")
    decide.add_argument("--goal", help="build the state from a goal instead of a file")
    decide.add_argument("--tool", help="intended tool for --goal state")
    decide.add_argument("--diff-file", help="diff to clip into --goal state")
    decide.add_argument("--tests", help="test summary for --goal state")
    decide.add_argument("--session-model", help="current chat model, for --goal state")
    decide.add_argument("--model", help=f"Jev model (default {schemas.DEFAULT_MODEL})")
    decide.add_argument(
        "--live",
        action="store_true",
        help=f"POST for real; also needs {LIVE_ENV}=1 and a key (see README)",
    )
    decide.add_argument(
        "--provider",
        choices=["experiential", "gateway", "direct", "typesafe", "openrouter"],
        help="force a provider instead of auto-detecting (sets JEV_PROVIDER)",
    )
    decide.add_argument(
        "--no-kimi-config",
        action="store_true",
        help="don't read providers.explabs from ~/.kimi-code/config.toml; env keys only",
    )
    decide.add_argument(
        "--candidates",
        help="comma-separated candidate ids for --pack decide (e.g. poll,push)",
    )
    decide.add_argument(
        "--no-escapes",
        action="store_true",
        help="for --pack decide: closed-world pick, no none/ask_human escape hatch",
    )
    decide.add_argument("--compact", action="store_true", help="one-line JSON output")
    decide.set_defaults(func=cmd_decide)

    packs = sub.add_parser("packs", help="list packs, their questions, and their advice words")
    packs.set_defaults(func=cmd_packs)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
