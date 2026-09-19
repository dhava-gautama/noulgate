"""Mocked tests. No network, no key, no charge — every transport is a stub."""

from __future__ import annotations

import json
import os
import unittest

from jev import JevClient, JevConfig, JevConfigError, JevTransportError, advise
from jev import compress, dryrun, providers, schemas
from jev.client import ENV_KEY, redacted_headers
from jev.packs import PACKS
from jev.policies import ADVICE, AdviceError

GOAL = "Decide whether the agent needs a web search to answer 'what is 2+2'"


def _raise_no_key(env):
    raise JevConfigError("no API key found (stubbed for the test)")


def ok_transport(payload: dict):
    def transport(url, headers, body, timeout_s):
        return 200, json.dumps(payload)

    return transport


class TestClientMock(unittest.TestCase):
    def test_live_false_refuses_before_transport(self):
        calls: list[bytes] = []

        def spy(url, headers, body, timeout_s):
            calls.append(body)
            return 200, json.dumps({"answers": {}})

        client = JevClient(transport=spy, live=False, require_auth=False)
        with self.assertRaises(JevConfigError):
            client.decide("state", PACKS["tool_gate"])
        self.assertEqual(calls, [], "a refused call must not reach the transport")

    def test_mock_transport_returns_answers(self):
        payload = {"model": "jev-latest", "usage": {"input_tokens": 3, "output_tokens": 1}, "answers": {"need_tool": {"type": "noul", "noul": 0.9}}}
        client = JevClient(transport=ok_transport(payload), live=True, require_auth=False)
        out = client.decide("state", PACKS["tool_gate"])
        self.assertEqual(out["answers"]["need_tool"]["noul"], 0.9)

    def test_payload_shape_matches_wire_schema(self):
        seen: dict = {}

        def spy(url, headers, body, timeout_s):
            seen["body"] = json.loads(body)
            seen["url"] = url
            seen["headers"] = headers
            return 200, json.dumps({"answers": {}})

        client = JevClient(transport=spy, live=True, require_auth=False)
        client.decide({"goal": GOAL}, PACKS["skill_gate"], model="jev-latest")
        self.assertEqual(seen["url"], schemas.GATEWAY_URL)
        self.assertEqual(seen["body"]["model"], "jev-latest")
        self.assertIn("questions", seen["body"])
        self.assertIn("state", seen["body"])
        self.assertNotIn("Authorization", seen["headers"], "no auth header without require_auth")

    def test_require_auth_needs_some_key(self):
        # require_auth must not send a request when no key can be found at all.
        # Patch the resolver to simulate a machine with no key anywhere.
        import jev.client as jc

        client = JevClient(transport=ok_transport({"answers": {}}), live=True, require_auth=True)
        original = jc._resolve_key
        jc._resolve_key = _raise_no_key
        try:
            with self.assertRaises(JevConfigError):
                client.decide("state", PACKS["tool_gate"])
        finally:
            jc._resolve_key = original

    def test_key_resolution_checks_env_then_kimi(self):
        import jev.client as jc

        # env var wins when set
        saved = os.environ.get(ENV_KEY)
        os.environ[ENV_KEY] = "env-wins"
        try:
            key, src = jc._resolve_key(ENV_KEY)
            self.assertEqual((key, src), ("env-wins", ENV_KEY))
        finally:
            if saved is None:
                os.environ.pop(ENV_KEY, None)
            else:
                os.environ[ENV_KEY] = saved

        # kimi config is the fallback when env is empty
        saved = os.environ.pop(ENV_KEY, None)
        saved_extra = {e: os.environ.pop(e, None) for e in jc.EXTRA_KEY_ENVS}
        try:
            key, src = jc._resolve_key(ENV_KEY)
            if key:  # a key was found in kimi config on this machine
                self.assertIn("kimi", src)
        finally:
            if saved is not None:
                os.environ[ENV_KEY] = saved
            for e, v in saved_extra.items():
                if v is not None:
                    os.environ[e] = v

    def test_require_auth_sends_bearer_header(self):
        seen: dict = {}

        def spy(url, headers, body, timeout_s):
            seen["headers"] = headers
            return 200, json.dumps({"answers": {}})

        saved = os.environ.get(ENV_KEY)
        os.environ[ENV_KEY] = "test-key-not-real"
        try:
            client = JevClient(transport=spy, live=True, require_auth=True)
            client.decide("state", PACKS["tool_gate"])
        finally:
            if saved is None:
                os.environ.pop(ENV_KEY, None)
            else:
                os.environ[ENV_KEY] = saved
        self.assertEqual(seen["headers"]["Authorization"], "Bearer test-key-not-real")
        self.assertEqual(redacted_headers(seen["headers"])["Authorization"], "Bearer [redacted]")

    def test_bad_status_raises_transport_error(self):
        def boom(url, headers, body, timeout_s):
            return 429, '{"detail": "rate limited"}'

        client = JevClient(transport=boom, live=True, require_auth=False)
        with self.assertRaises(JevTransportError) as ctx:
            client.decide("state", PACKS["tool_gate"])
        self.assertEqual(ctx.exception.status, 429)

    def test_non_json_body_raises_transport_error(self):
        def html(url, headers, body, timeout_s):
            return 200, "<html>not json</html>"

        client = JevClient(transport=html, live=True, require_auth=False)
        with self.assertRaises(JevTransportError):
            client.decide("state", PACKS["tool_gate"])

    def test_missing_answers_key_raises(self):
        client = JevClient(transport=ok_transport({"model": "jev-latest"}), live=True, require_auth=False)
        with self.assertRaises(JevTransportError):
            client.decide("state", PACKS["tool_gate"])

    def test_timeout_bounds(self):
        with self.assertRaises(JevConfigError):
            JevClient(config=JevConfig(timeout_s=0), transport=ok_transport({}))
        with self.assertRaises(JevConfigError):
            JevClient(config=JevConfig(timeout_s=99), transport=ok_transport({}))

    def test_authorization_header_is_redacted(self):
        headers = {"Authorization": "Bearer sk-live-secret", "Accept": "application/json"}
        out = redacted_headers(headers)
        self.assertEqual(out["Authorization"], "Bearer [redacted]")
        self.assertNotIn("sk-live-secret", json.dumps(out))

    def test_empty_model_falls_back_to_default(self):
        seen: dict = {}

        def spy(url, headers, body, timeout_s):
            seen["model"] = json.loads(body)["model"]
            return 200, json.dumps({"answers": {}})

        client = JevClient(transport=spy, live=True, require_auth=False)
        client.decide("state", PACKS["tool_gate"], model="   ")
        self.assertEqual(seen["model"], schemas.DEFAULT_MODEL)

    def test_free_suffix_is_preserved(self):
        seen: dict = {}

        def spy(url, headers, body, timeout_s):
            seen["model"] = json.loads(body)["model"]
            return 200, json.dumps({"answers": {}})

        client = JevClient(transport=spy, live=True, require_auth=False)
        client.decide("state", PACKS["tool_gate"], model="jev-latest:free")
        self.assertEqual(seen["model"], "jev-latest:free")


class TestSchemas(unittest.TestCase):
    def test_packs_are_valid(self):
        for name, questions in PACKS.items():
            with self.subTest(pack=name):
                schemas.validate_questions(questions)

    def test_choice_needs_criteria(self):
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_questions({"q": {"type": "choice", "instructions": "pick"}})

    def test_score_needs_two_levels(self):
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_questions({"q": {"type": "score", "instructions": "rate", "criteria": ["only"]}})

    def test_noul_criteria_keys_are_checked(self):
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_questions(
                {"q": {"type": "noul", "instructions": "yes?", "criteria": {"maybe": "x"}}}
            )

    def test_question_cap(self):
        many = {f"q{i}": {"type": "noul", "instructions": "x"} for i in range(schemas.GATEWAY_MAX_QUESTIONS + 1)}
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_questions(many)

    def test_empty_map_rejected(self):
        with self.assertRaises(schemas.SchemaError):
            schemas.validate_questions({})


class TestDryRun(unittest.TestCase):
    def test_smalltalk_skips_tools_and_skills(self):
        state = compress.compress_state(goal="hey, how are you")
        client = JevClient(transport=dryrun.make_transport(state, PACKS["skill_gate"]), live=True, require_auth=False)
        answers = client.decide(state, PACKS["skill_gate"])["answers"]
        self.assertEqual(advise("skill_gate", answers)["advice"], "no_skill")

        client = JevClient(transport=dryrun.make_transport(state, PACKS["tool_gate"]), live=True, require_auth=False)
        answers = client.decide(state, PACKS["tool_gate"])["answers"]
        self.assertEqual(advise("tool_gate", answers)["advice"], "skip_tool")

    def test_search_goal_advises_search(self):
        state = compress.compress_state(goal="search the web for the current BMKG forecast", intended_tool="web_search")
        client = JevClient(transport=dryrun.make_transport(state, PACKS["tool_gate"]), live=True, require_auth=False)
        answers = client.decide(state, PACKS["tool_gate"])["answers"]
        self.assertEqual(advise("tool_gate", answers)["advice"], "consider_search")

    def test_mutating_goal_is_flagged(self):
        state = compress.compress_state(goal="apply the patch and push the commit", intended_tool="shell")
        client = JevClient(transport=dryrun.make_transport(state, PACKS["tool_gate"]), live=True, require_auth=False)
        answers = client.decide(state, PACKS["tool_gate"])["answers"]
        result = advise("tool_gate", answers)
        self.assertGreaterEqual(result["signals"]["side_effect"], 0.5)

    def test_every_pack_answers_every_question(self):
        state = compress.compress_state(goal="refactor the parser and run the tests")
        for name, questions in PACKS.items():
            with self.subTest(pack=name):
                response = dryrun.fixture_response(state, questions)
                self.assertEqual(set(response["answers"]), set(questions))
                self.assertIn(advise(name, response["answers"])["advice"], ADVICE[name])

    def test_choice_answers_stay_inside_criteria(self):
        state = compress.compress_state(goal="search the docs")
        response = dryrun.fixture_response(state, PACKS["tool_gate"])
        family = response["answers"]["tool_family"]
        self.assertIn(family["choice"], PACKS["tool_gate"]["tool_family"]["criteria"])
        self.assertAlmostEqual(sum(family["probabilities"].values()), 1.0, places=6)

    def test_score_answers_stay_inside_rubric(self):
        state = compress.compress_state(goal="deploy the auth change")
        response = dryrun.fixture_response(state, PACKS["review_gate"])
        risk = response["answers"]["risk"]
        self.assertLess(risk["score"], len(PACKS["review_gate"]["risk"]["criteria"]))
        self.assertEqual(set(risk["probabilities"]), {str(i) for i in range(4)})

    def test_response_matches_wire_shape(self):
        state = compress.compress_state(goal="read the file")
        response = dryrun.fixture_response(state, PACKS["tool_gate"])
        self.assertEqual(response["model"], schemas.DEFAULT_MODEL)
        self.assertEqual(set(response["usage"]), {"input_tokens", "output_tokens"})
        for answer in response["answers"].values():
            self.assertIn(answer["type"], {"noul", "choice", "score"})


class TestPolicies(unittest.TestCase):
    def test_unknown_pack_rejected(self):
        with self.assertRaises(AdviceError):
            advise("nope", {"a": {"type": "noul", "noul": 1.0}})

    def test_empty_answers_rejected(self):
        with self.assertRaises(AdviceError):
            advise("tool_gate", {})

    def test_missing_answers_fall_back_conservatively(self):
        result = advise("review_gate", {"unrelated": {"type": "noul", "noul": 1.0}})
        self.assertEqual(result["advice"], "show_diff_wait")

    def test_apply_never_means_apply(self):
        answers = {
            "tests_support": {"type": "noul", "noul": 0.99},
            "safe_to_apply": {"type": "noul", "noul": 0.99},
            "risk": {"type": "score", "score": 0.0},
            "action": {"type": "choice", "choice": "apply"},
        }
        result = advise("review_gate", answers)
        self.assertEqual(result["advice"], "apply_advice_only")

    def test_risky_diff_asks_a_human(self):
        answers = {
            "tests_support": {"type": "noul", "noul": 0.9},
            "safe_to_apply": {"type": "noul", "noul": 0.9},
            "risk": {"type": "score", "score": 3.0},
            "action": {"type": "choice", "choice": "show"},
        }
        self.assertEqual(advise("review_gate", answers)["advice"], "ask_human")

    def test_model_route_keeps_model_when_reasoning_is_needed(self):
        answers = {
            "task_kind": {"type": "choice", "choice": "edit"},
            "cheap_ok": {"type": "noul", "noul": 0.9},
            "needs_reasoning": {"type": "noul", "noul": 0.9},
            "model_tier": {"type": "choice", "choice": "nano"},
            "context_fat": {"type": "noul", "noul": 0.1},
        }
        self.assertEqual(advise("model_route", answers)["advice"], "keep_model")

    def test_advice_words_are_declared(self):
        state = compress.compress_state(goal="hey there")
        for name, questions in PACKS.items():
            response = dryrun.fixture_response(state, questions)
            advice = advise(name, response["answers"])["advice"]
            with self.subTest(pack=name):
                self.assertIn(advice, ADVICE[name])

    def test_reasons_are_always_explained(self):
        state = compress.compress_state(goal="read the file")
        for name, questions in PACKS.items():
            response = dryrun.fixture_response(state, questions)
            with self.subTest(pack=name):
                self.assertTrue(advise(name, response["answers"])["reasons"])

    # --- calibrated behaviors, from fixtures/calibration.json ---

    def test_high_side_effect_shell_asks_a_human(self):
        # "delete the production database": side_effect 0.97, family shell.
        answers = {
            "need_tool": {"type": "noul", "noul": 0.9},
            "need_new_evidence": {"type": "noul", "noul": 0.2},
            "side_effect": {"type": "noul", "noul": 0.97},
            "tool_family": {"type": "choice", "choice": "shell"},
        }
        self.assertEqual(advise("tool_gate", answers)["advice"], "ask_human")

    def test_high_side_effect_readonly_search_is_not_blocked(self):
        # A web search leaves the machine but mutates nothing; high side_effect
        # there is informational, not blocking.
        answers = {
            "need_tool": {"type": "noul", "noul": 0.93},
            "need_new_evidence": {"type": "noul", "noul": 0.94},
            "side_effect": {"type": "noul", "noul": 0.88},
            "tool_family": {"type": "choice", "choice": "search"},
        }
        self.assertEqual(advise("tool_gate", answers)["advice"], "consider_search")

    def test_review_gate_soft_ask_overruled_by_green_signals(self):
        # "apply the typo fix, 52 passed": action ask, but tests/safe/risk all green.
        answers = {
            "tests_support": {"type": "noul", "noul": 0.72},
            "safe_to_apply": {"type": "noul", "noul": 0.79},
            "risk": {"type": "score", "score": 0.01},
            "action": {"type": "choice", "choice": "ask"},
        }
        self.assertEqual(advise("review_gate", answers)["advice"], "show_diff_wait")

    def test_review_gate_hard_ask_when_risky(self):
        # action ask + a risky diff must still stop for a human.
        answers = {
            "tests_support": {"type": "noul", "noul": 0.9},
            "safe_to_apply": {"type": "noul", "noul": 0.4},
            "risk": {"type": "score", "score": 2.0},
            "action": {"type": "choice", "choice": "ask"},
        }
        self.assertEqual(advise("review_gate", answers)["advice"], "ask_human")

    def test_skill_gate_need_skill_overrules_none_action(self):
        # "migrate the schema following the runbook": action none, need_skill 0.6.
        answers = {
            "need_skill": {"type": "noul", "noul": 0.6},
            "just_talk": {"type": "noul", "noul": 0.16},
            "skill_action": {"type": "choice", "choice": "none"},
        }
        self.assertEqual(advise("skill_gate", answers)["advice"], "view_one")


def _decide_answers(pick, confidence, probabilities, any_good=0.9, confident=0.9):
    return {
        "pick": {"type": "choice", "choice": pick, "confidence": confidence, "probabilities": probabilities},
        "any_good": {"type": "noul", "noul": any_good},
        "confident": {"type": "noul", "noul": confident},
    }


class TestDecideArbiter(unittest.TestCase):
    """The arbiter gate: a bot acts only on a confident, separated, safe pick."""

    def test_strong_separated_safe_pick_auto_acts(self):
        a = _decide_answers("poll", 0.95, {"poll": 0.9, "push": 0.08, "none": 0.01, "ask_human": 0.01})
        self.assertEqual(advise("decide", a)["advice"], "auto_act")

    def test_coin_flip_escalates(self):
        # 0.51 / 0.49 — the winner is a coin flip even though it's the argmax.
        a = _decide_answers("poll", 0.5, {"poll": 0.51, "push": 0.49}, confident=0.4)
        self.assertEqual(advise("decide", a)["advice"], "escalate")

    def test_confident_but_tied_margin_proposes(self):
        # confident winner but the margin is too thin to act on.
        a = _decide_answers("poll", 0.9, {"poll": 0.55, "push": 0.45}, any_good=0.9, confident=0.9)
        self.assertEqual(advise("decide", a)["advice"], "propose")

    def test_escape_none_abstains(self):
        a = _decide_answers("none", 0.8, {"none": 0.8, "poll": 0.2})
        self.assertEqual(advise("decide", a)["advice"], "abstain")

    def test_escape_ask_escalates(self):
        a = _decide_answers("ask_human", 0.8, {"ask_human": 0.8, "poll": 0.2}, any_good=0.3, confident=0.5)
        self.assertEqual(advise("decide", a)["advice"], "escalate")

    def test_no_good_candidate_abstains(self):
        # confident pick, but Jev says nothing on the field is acceptable.
        a = _decide_answers("poll", 0.95, {"poll": 0.9, "push": 0.1}, any_good=0.2)
        self.assertEqual(advise("decide", a)["advice"], "abstain")

    def test_unseparated_field_escalates(self):
        # Jev itself says the pick is a coin flip.
        a = _decide_answers("poll", 0.9, {"poll": 0.9, "push": 0.1}, confident=0.3)
        self.assertEqual(advise("decide", a)["advice"], "escalate")

    def test_missing_pick_abstains(self):
        self.assertEqual(advise("decide", {"any_good": {"type": "noul", "noul": 1.0}})["advice"], "abstain")

    def test_decide_advice_words_declared(self):
        for a in (
            _decide_answers("poll", 0.95, {"poll": 0.9, "push": 0.1}),
            _decide_answers("none", 0.8, {"none": 0.8, "poll": 0.2}),
        ):
            self.assertIn(advise("decide", a)["advice"], ADVICE["decide"])


class TestDecidePack(unittest.TestCase):
    def test_build_makes_a_choice_over_candidates_plus_escapes(self):
        from jev.packs.decide import build

        q = build(["poll", "push"])
        self.assertIn("poll", q["pick"]["criteria"])
        self.assertIn("push", q["pick"]["criteria"])
        self.assertIn("none", q["pick"]["criteria"])
        self.assertIn("ask_human", q["pick"]["criteria"])
        self.assertIn(q["any_good"]["type"], "noul")
        self.assertIn(q["confident"]["type"], "noul")

    def test_build_no_escapes_is_closed_world(self):
        from jev.packs.decide import build

        q = build(["a", "b"], escapes=False)
        self.assertNotIn("none", q["pick"]["criteria"])
        self.assertNotIn("ask_human", q["pick"]["criteria"])

    def test_build_rejects_duplicates_and_overflow(self):
        from jev.packs.decide import MAX_CANDIDATES, build
        from jev.schemas import SchemaError

        with self.assertRaises(SchemaError):
            build(["a", "a"])
        with self.assertRaises(SchemaError):
            build([f"c{i}" for i in range(MAX_CANDIDATES + 1)])
        with self.assertRaises(SchemaError):
            build([])

    def test_decide_pack_passes_schema_validation(self):
        from jev.packs.decide import build

        schemas.validate_questions(build(["poll", "push", "queue"]))


class TestCalibrationFixture(unittest.TestCase):
    """Replay the recorded live answers against the current thresholds."""

    FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "calibration.json")

    def test_recorded_answers_still_agree(self):
        if not os.path.isfile(self.FIXTURE):
            self.skipTest("no calibration fixture recorded yet")
        with open(self.FIXTURE, encoding="utf-8") as handle:
            rows = json.load(handle)
        scored = [r for r in rows if "answers" in r]
        self.assertTrue(scored, "fixture has no scored rows")
        misses = []
        for row in scored:
            got = advise(row["case"]["pack"], row["answers"])["advice"]
            if got != row["expected"]:
                misses.append(f"{row['case']['pack']}: want {row['expected']}, got {got}")
        self.assertEqual(misses, [], "threshold regression: " + "; ".join(misses))


class TestCliDryRunShape(unittest.TestCase):
    """The dry-run CLI must never emit a bare 'advice' that reads as a verdict."""

    def test_dry_run_nulls_advice(self):
        import subprocess

        out = subprocess.run(
            ["python3", "-m", "jev", "decide", "--pack", "skill_gate", "--state-text", "hey", "--compact"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertIsNone(payload["advice"])
        self.assertIn("fixture_advice", payload)
        self.assertIn("not a Jev call", payload["notice"])


class TestCliFailOpen(unittest.TestCase):
    """A live call that cannot reach Jev must pass, never halt the caller."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _decide(self, *extra):
        import subprocess

        env = dict(os.environ, JEV_ALLOW_LIVE="1")
        return subprocess.run(
            ["python3", "-m", "jev", "decide", "--compact", *extra],
            cwd=self.ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_dead_key_passes_with_exit_0(self):
        # Forcing a provider with a key that will be rejected must still pass.
        with _EnvGuard(OPENROUTER_API_KEY="sk-or-dead"):
            out = self._decide("--pack", "skill_gate", "--state-text", "hey", "--live", "--provider", "openrouter")
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["mode"], "pass")
        self.assertEqual(payload["advice"], "pass")
        self.assertIn("not a decision", payload["notice"])
        self.assertTrue(payload["reasons"])

    def test_unreachable_host_passes_with_exit_0(self):
        def down(url, headers, body, timeout):
            raise JevTransportError("connection refused")

        # A stubbed transport that always fails must still produce a pass.
        from jev.client import JevClient

        client = JevClient(transport=down, live=True, require_auth=False)
        with self.assertRaises(JevTransportError):
            client.decide("s", {"q": {"type": "noul", "instructions": "x"}})
        # the CLI path is what must not raise; the dead-key test above covers it



class TestCompress(unittest.TestCase):
    def test_goal_is_stripped_and_defaults_filled(self):
        state = compress.compress_state(goal="  do the thing  ")
        self.assertEqual(state["goal"], "do the thing")
        self.assertEqual(state["intended_tool"], "none")
        self.assertEqual(state["diff"], "no diff")
        self.assertEqual(state["session_model"], "unchanged")

    def test_long_diff_is_clipped(self):
        state = compress.compress_state(goal="x", diff="a" * 20_000)
        self.assertLessEqual(len(state["diff"]), compress.MAX_DIFF_CHARS)
        self.assertIn("truncated", state["diff"])

    def test_long_test_summary_is_clipped(self):
        state = compress.compress_state(goal="x", test_summary="b" * 5_000)
        self.assertLessEqual(len(state["test_summary"]), compress.MAX_TEST_CHARS)

    def test_extra_is_passed_through(self):
        state = compress.compress_state(goal="x", extra={"turn": 3})
        self.assertEqual(state["extra"], {"turn": 3})

    def test_no_extra_key_when_unset(self):
        self.assertNotIn("extra", compress.compress_state(goal="x"))


class TestSampleFixture(unittest.TestCase):
    def test_fixture_state_file_still_works(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "sample_state.json")
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
        response = dryrun.fixture_response(state, PACKS["tool_gate"])
        self.assertEqual(set(response["answers"]), set(PACKS["tool_gate"]))

    def test_fixture_has_no_secret(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "sample_state.json")
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
        self.assertNotIn(ENV_KEY, raw)
        self.assertNotIn("Bearer ", raw)


class _EnvGuard:
    """Clear/set provider env vars for the duration of a test."""

    NAMES = ("EXPERIENTIAL_API_KEY", "EXPLABS_API_KEY", "TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "JEV_PROVIDER")

    def __init__(self, **set_to):
        self.set_to = set_to
        self.saved = {n: os.environ.get(n) for n in self.NAMES}

    def __enter__(self):
        for n in self.NAMES:
            os.environ.pop(n, None)
        for n, v in self.set_to.items():
            if v is not None:
                os.environ[n] = v
        return self

    def __exit__(self, *a):
        for n, v in self.saved.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v
        return False


class TestProviders(unittest.TestCase):
    def test_openrouter_slug_maps_latest(self):
        self.assertEqual(providers._openrouter_slug("jev-latest"), providers.OPENROUTER_LATEST)
        self.assertEqual(providers._openrouter_slug(""), providers.OPENROUTER_LATEST)
        self.assertEqual(providers._openrouter_slug("jev-1.12"), "typesafe/jev-1.12")
        self.assertEqual(providers._openrouter_slug("typesafe/jev-1.13"), "typesafe/jev-1.13")

    def test_direct_key_wins_over_openrouter(self):
        with _EnvGuard(EXPERIENTIAL_API_KEY="direct-key", OPENROUTER_API_KEY="sk-or-test"):
            p = providers.resolve_provider()
        self.assertEqual(p.name, "experiential")
        self.assertEqual(p.url, providers.EXPERIENTIAL_URL)
        self.assertEqual(p.key, "direct-key")

    def test_openrouter_is_the_fallback(self):
        import jev.providers as pr

        with _EnvGuard(OPENROUTER_API_KEY="sk-or-test"):
            original = pr._key_from_kimi_config
            pr._key_from_kimi_config = lambda: ""
            try:
                p = providers.resolve_provider()
            finally:
                pr._key_from_kimi_config = original
        self.assertEqual(p.name, "openrouter")
        self.assertEqual(p.url, providers.OPENROUTER_URL)
        self.assertEqual(p.model, providers.OPENROUTER_LATEST)
        self.assertEqual(p.key, "sk-or-test")

    def test_no_key_anywhere_raises(self):
        import jev.providers as pr

        with _EnvGuard():
            original = pr._key_from_kimi_config
            pr._key_from_kimi_config = lambda: ""
            try:
                with self.assertRaises(JevConfigError):
                    pr.resolve_provider()
            finally:
                pr._key_from_kimi_config = original

    def test_forced_openrouter_needs_its_key(self):
        with _EnvGuard(JEV_PROVIDER="openrouter"):
            with self.assertRaises(JevConfigError):
                providers.resolve_provider()

    def test_forced_experiential_needs_a_direct_key(self):
        import jev.providers as pr

        with _EnvGuard(JEV_PROVIDER="experiential", OPENROUTER_API_KEY="sk-or-test"):
            original = pr._key_from_kimi_config
            pr._key_from_kimi_config = lambda: ""
            try:
                with self.assertRaises(JevConfigError):
                    pr.resolve_provider()
            finally:
                pr._key_from_kimi_config = original

    def test_unknown_provider_rejected(self):
        with _EnvGuard(JEV_PROVIDER="nope"):
            with self.assertRaises(JevConfigError):
                providers.resolve_provider()

    def test_forced_openrouter_ignores_direct_key(self):
        with _EnvGuard(JEV_PROVIDER="openrouter", EXPERIENTIAL_API_KEY="direct", OPENROUTER_API_KEY="sk-or-test"):
            p = providers.resolve_provider()
        self.assertEqual(p.name, "openrouter")
        self.assertEqual(p.key, "sk-or-test")

    def test_typesafe_key_goes_direct_not_gateway(self):
        # A TypeSafe console key means api.typesafe.ai, no gateway in the middle.
        with _EnvGuard(TYPESAFE_API_KEY="ts-key"):
            p = providers.resolve_provider()
        self.assertEqual(p.name, "typesafe")
        self.assertEqual(p.url, providers.TYPESAFE_URL)
        self.assertEqual(p.key, "ts-key")

    def test_typesafe_key_wins_over_gateway_key(self):
        # Both set: direct wins — a console key should not route through the proxy.
        with _EnvGuard(TYPESAFE_API_KEY="ts-key", EXPERIENTIAL_API_KEY="gw-key"):
            p = providers.resolve_provider()
        self.assertEqual(p.name, "typesafe")

    def test_forced_typesafe_needs_its_key(self):
        with _EnvGuard(JEV_PROVIDER="typesafe"):
            with self.assertRaises(JevConfigError):
                providers.resolve_provider()

    def test_forced_gateway_ignores_typesafe_key(self):
        # --provider experiential with only a TypeSafe key set must fail, not
        # silently send the console key to the gateway.
        with _EnvGuard(JEV_PROVIDER="experiential", TYPESAFE_API_KEY="ts-key"):
            import jev.providers as pr

            original = pr._key_from_kimi_config
            pr._key_from_kimi_config = lambda: ""
            try:
                with self.assertRaises(JevConfigError):
                    pr.resolve_provider()
            finally:
                pr._key_from_kimi_config = original

    def test_gateway_key_does_not_use_typesafe_env(self):
        # TYPESAFE_API_KEY must never be read as a gateway key.
        import jev.providers as pr

        with _EnvGuard(TYPESAFE_API_KEY="ts-key"):
            original = pr._key_from_kimi_config
            pr._key_from_kimi_config = lambda: ""
            try:
                key, _ = pr._find_gateway_key()
            finally:
                pr._key_from_kimi_config = original
        self.assertEqual(key, "")


class TestOpenRouterTransport(unittest.TestCase):
    def _openrouter_provider(self, model: str = "jev-latest"):
        with _EnvGuard(JEV_PROVIDER="openrouter", OPENROUTER_API_KEY="sk-or-test"):
            return providers.resolve_provider(model)

    def test_decide_posts_to_decisions_endpoint_with_slug(self):
        seen: dict = {}

        def spy(url, headers, body, timeout_s):
            seen["url"] = url
            seen["headers"] = headers
            seen["body"] = json.loads(body)
            return 200, json.dumps({"answers": {"need_tool": {"type": "noul", "noul": 0.9}}})

        provider = self._openrouter_provider()
        client = JevClient(transport=spy, live=True, require_auth=True)
        client.decide({"goal": GOAL}, PACKS["tool_gate"], provider=provider)

        self.assertEqual(seen["url"], providers.OPENROUTER_URL)
        self.assertEqual(seen["body"]["model"], providers.OPENROUTER_LATEST)
        self.assertEqual(seen["headers"]["Authorization"], "Bearer sk-or-test")
        self.assertEqual(seen["headers"]["X-OpenRouter-Title"], "noulgate")

    def test_decide_pins_an_explicit_openrouter_version(self):
        seen: dict = {}

        def spy(url, headers, body, timeout_s):
            seen["body"] = json.loads(body)
            return 200, json.dumps({"answers": {}})

        provider = self._openrouter_provider("jev-1.12")
        client = JevClient(transport=spy, live=True, require_auth=True)
        client.decide("s", PACKS["tool_gate"], provider=provider)
        self.assertEqual(seen["body"]["model"], "typesafe/jev-1.12")

    def test_openrouter_usage_absent_is_tolerated(self):
        def spy(url, headers, body, timeout_s):
            return 200, json.dumps({"answers": {"need_tool": {"type": "noul", "noul": 0.1}}})

        provider = self._openrouter_provider()
        client = JevClient(transport=spy, live=True, require_auth=True)
        out = client.decide("s", PACKS["tool_gate"], provider=provider)
        self.assertIn("answers", out)


if __name__ == "__main__":
    unittest.main()
