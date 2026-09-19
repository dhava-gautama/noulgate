"""Where a live call goes: the Experiential gateway, TypeSafe direct, or OpenRouter.

Jev is TypeSafe's model. It is reachable three ways, all speaking the same
``{model, state, questions}`` → ``{answers, usage}`` contract:

- **Experiential gateway** (default): a managed proxy in front of TypeSafe. Key
  envs ``EXPERIENTIAL_API_KEY`` / ``EXPLABS_API_KEY``, or kimi-code's
  ``providers.explabs``. The response carries ``"provider": "typesafe"`` — the
  gateway forwards upstream.
- **TypeSafe direct**: ``api.typesafe.ai``, the official API. Key env
  ``TYPESAFE_API_KEY``. Use this when you have a TypeSafe console key and want no
  gateway in the middle.
- **OpenRouter**: the Decisions API. Key env ``OPENROUTER_API_KEY``.

The client does not care which it is handed — the payload is identical either way.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .client import ENV_KEY, JevConfigError, _key_from_kimi_config

PROVIDER_ENV = "JEV_PROVIDER"

EXPERIENTIAL_URL = "https://api.experientiallabs.ai/v1/systemone"
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
OPENROUTER_URL = "https://openrouter.ai/api/alpha/decisions"

DEFAULT_MODEL = "jev-latest"
# OpenRouter has no redirecting "latest" slug; map it to the current release.
# Pin an exact version with JEV_MODEL when that matters.
OPENROUTER_LATEST = "typesafe/jev-1.13"

OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"
TYPESAFE_KEY_ENV = "TYPESAFE_API_KEY"
# Gateway key envs, checked in this order. TYPESAFE_API_KEY is NOT here: it is
# the key for the TypeSafe-direct provider, not the gateway.
GATEWAY_KEY_ENVS = (ENV_KEY, "EXPLABS_API_KEY")


@dataclass(frozen=True)
class Provider:
    name: str
    url: str
    key_env: str
    model: str
    key: str
    key_source: str


def _openrouter_slug(model: str) -> str:
    raw = model.strip()
    if not raw or raw == DEFAULT_MODEL:
        return OPENROUTER_LATEST
    return raw if raw.startswith("typesafe/") else f"typesafe/{raw}"


def _find_gateway_key(use_kimi_config: bool = True) -> tuple[str, str]:
    for env in GATEWAY_KEY_ENVS:
        key = os.environ.get(env, "").strip()
        if key:
            return key, env
    if use_kimi_config:
        key = _key_from_kimi_config()
        if key:
            return key, "kimi-code config (providers.explabs)"
    return "", ""


def _find_typesafe_key() -> tuple[str, str]:
    key = os.environ.get(TYPESAFE_KEY_ENV, "").strip()
    if key:
        return key, TYPESAFE_KEY_ENV
    return "", ""


def _find_openrouter_key() -> tuple[str, str]:
    key = os.environ.get(OPENROUTER_KEY_ENV, "").strip()
    if key:
        return key, OPENROUTER_KEY_ENV
    return "", ""


def resolve_provider(model: str = DEFAULT_MODEL, use_kimi_config: bool = True) -> Provider:
    """Pick a provider and a key, never printing the key.

    ``JEV_PROVIDER`` forces one (``experiential``/``gateway``, ``typesafe``, or
    ``openrouter``). Otherwise: a TypeSafe console key goes direct (no gateway in
    the middle), a gateway key uses Experiential, and OpenRouter is the fallback.
    ``use_kimi_config=False`` skips the kimi-code config fallback. Raises
    :class:`JevConfigError` when no provider can be satisfied.
    """
    forced = os.environ.get(PROVIDER_ENV, "").strip().lower()
    if forced in {"experiential", "gateway", "direct"}:
        return _experiential(model, use_kimi_config)
    if forced == "typesafe":
        return _typesafe(model)
    if forced == "openrouter":
        return _openrouter(model)
    if forced:
        raise JevConfigError(
            f"unknown {PROVIDER_ENV} {forced!r}; use experiential|typesafe|openrouter"
        )

    # A TypeSafe console key means go direct — no gateway in the middle.
    key, source = _find_typesafe_key()
    if key:
        return Provider("typesafe", TYPESAFE_URL, TYPESAFE_KEY_ENV, model, key, source)
    key, source = _find_gateway_key(use_kimi_config)
    if key:
        return Provider("experiential", EXPERIENTIAL_URL, GATEWAY_KEY_ENVS[0], model, key, source)
    return _openrouter(model)


def _experiential(model: str, use_kimi_config: bool = True) -> Provider:
    key, source = _find_gateway_key(use_kimi_config)
    if not key:
        where = f"one of {GATEWAY_KEY_ENVS}"
        if use_kimi_config:
            where += " or providers.explabs in ~/.kimi-code/config.toml"
        raise JevConfigError(
            f"{PROVIDER_ENV}=experiential but no gateway key found. Set {where}."
        )
    return Provider("experiential", EXPERIENTIAL_URL, GATEWAY_KEY_ENVS[0], model, key, source)


def _typesafe(model: str) -> Provider:
    key, source = _find_typesafe_key()
    if not key:
        raise JevConfigError(
            f"{PROVIDER_ENV}=typesafe but {TYPESAFE_KEY_ENV} is not set. "
            "Get one at console.typesafe.ai/settings/keys."
        )
    return Provider("typesafe", TYPESAFE_URL, TYPESAFE_KEY_ENV, model, key, source)


def _openrouter(model: str) -> Provider:
    key, source = _find_openrouter_key()
    if not key:
        raise JevConfigError(
            f"no API key found. Set {OPENROUTER_KEY_ENV} for OpenRouter, "
            f"{TYPESAFE_KEY_ENV} for TypeSafe direct, or one of {GATEWAY_KEY_ENVS} "
            "(or providers.explabs in ~/.kimi-code/config.toml) for the gateway."
        )
    return Provider("openrouter", OPENROUTER_URL, OPENROUTER_KEY_ENV, _openrouter_slug(model), key, source)
