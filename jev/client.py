"""Native HTTP client for Experiential /v1/systemone.

No retries. No Idempotency-Key. No streaming. No chat facades.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from . import schemas

DEFAULT_TIMEOUT_S = 12.0
MAX_TIMEOUT_S = 30.0
ENV_KEY = "EXPERIENTIAL_API_KEY"
# Gateway alternates checked when EXPERIENTIAL_API_KEY is not set. TYPESAFE_API_KEY
# is deliberately absent: it is the key for the TypeSafe-direct provider
# (api.typesafe.ai), not this gateway.
EXTRA_KEY_ENVS = ("EXPLABS_API_KEY",)
# kimi-code stores provider keys in its own config; the helper reads the one
# named "explabs" so a configured CLI "just works" without a second export.
KIMI_CONFIG = Path.home() / ".kimi-code" / "config.toml"


class JevConfigError(RuntimeError):
    pass


class JevTransportError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass(frozen=True)
class JevConfig:
    url: str = schemas.GATEWAY_URL
    model: str = schemas.DEFAULT_MODEL
    timeout_s: float = DEFAULT_TIMEOUT_S
    api_key_env: str = ENV_KEY

    @classmethod
    def from_env(cls) -> "JevConfig":
        """A config honouring JEV_URL / JEV_MODEL overrides for non-default gateways."""
        return cls(
            url=os.environ.get("JEV_URL", schemas.GATEWAY_URL),
            model=os.environ.get("JEV_MODEL", schemas.DEFAULT_MODEL),
        )


Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, str]]


def _default_transport(url: str, headers: dict[str, str], body: bytes, timeout_s: float) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise JevTransportError(
            f"HTTP {exc.code} from systemone",
            status=exc.code,
            body=raw[:2000],
        ) from exc
    except urllib.error.URLError as exc:
        raise JevTransportError(f"transport error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise JevTransportError(f"timeout after {timeout_s}s") from exc


def _normalize_model(model: str) -> str:
    """Keep jev-latest. Preserve an explicit :free (or other) suffix if selected."""
    raw = model.strip()
    if not raw:
        return schemas.DEFAULT_MODEL
    return raw


class JevClient:
    def __init__(
        self,
        config: JevConfig | None = None,
        transport: Transport | None = None,
        live: bool = False,
        require_auth: bool | None = None,
    ) -> None:
        self.config = config or JevConfig()
        if self.config.timeout_s <= 0 or self.config.timeout_s > MAX_TIMEOUT_S:
            raise JevConfigError(f"timeout must be in (0, {MAX_TIMEOUT_S}]")
        self.transport = transport or _default_transport
        self.live = live
        self.require_auth = live if require_auth is None and transport is None else bool(require_auth)

    def decide(
        self,
        state: str | Mapping[str, Any] | list[Any],
        questions: Mapping[str, Any],
        model: str | None = None,
        provider: Any | None = None,
    ) -> dict[str, Any]:
        schemas.validate_questions(questions)
        payload = {
            "model": _normalize_model(model or self.config.model),
            "state": state,
            "questions": dict(questions),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if not self.live:
            raise JevConfigError(
                "refusing POST (client.live is False). "
                "Use a mock transport with live=True, or approve a charged call."
            )
        url = self.config.url
        if provider is not None:
            # A resolved Provider carries its own url, key, and model slug.
            url = provider.url
            payload["model"] = provider.model
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Authorization"] = f"Bearer {provider.key}"
            if provider.name == "openrouter":
                headers["HTTP-Referer"] = "https://github.com/dhava-gautama/noulgate"
                headers["X-OpenRouter-Title"] = "noulgate"
        elif self.require_auth:
            key, _source = _resolve_key(self.config.api_key_env)
            headers["Authorization"] = f"Bearer {key}"

        status, raw = self.transport(
            url, headers, body, self.config.timeout_s
        )
        if status != 200:
            raise JevTransportError(f"HTTP {status} from systemone", status=status, body=raw[:2000])
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise JevTransportError("systemone returned non-JSON", status=status, body=raw[:500]) from exc
        if not isinstance(parsed, dict) or "answers" not in parsed:
            raise JevTransportError("systemone JSON missing answers", status=status, body=raw[:500])
        return parsed


def _resolve_key(api_key_env: str) -> tuple[str, str]:
    """Find an API key without ever printing it.

    Checks, in order: the configured env var, the well-known alternates, then
    the kimi-code provider config. Returns ``(key, source)``; raises on miss.
    """
    key = os.environ.get(api_key_env, "").strip()
    if key:
        return key, api_key_env
    for env in EXTRA_KEY_ENVS:
        key = os.environ.get(env, "").strip()
        if key:
            return key, env
    key = _key_from_kimi_config()
    if key:
        return key, "kimi-code config (providers.explabs)"
    raise JevConfigError(
        f"no API key found. Set {api_key_env}, one of {EXTRA_KEY_ENVS}, or "
        "add providers.explabs to ~/.kimi-code/config.toml. I will not ask you "
        "to paste it."
    )


def _key_from_kimi_config() -> str:
    """Read the explabs key from kimi-code's own config, if present."""
    if not KIMI_CONFIG.is_file():
        return ""
    try:
        import tomllib

        data = tomllib.loads(KIMI_CONFIG.read_text(encoding="utf-8"))
        explabs = data.get("providers", {}).get("explabs", {})
        return str(explabs.get("api_key", "")).strip()
    except Exception:
        return ""


def redacted_headers(headers: Mapping[str, str]) -> dict[str, str]:
    out = dict(headers)
    if "Authorization" in out:
        out["Authorization"] = "Bearer [redacted]"
    return out
