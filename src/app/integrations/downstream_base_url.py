from __future__ import annotations

import os
from typing import NoReturn
from urllib.parse import SplitResult, urlsplit

_ALLOWED_SCHEMES = {"http", "https"}


def resolve_downstream_base_url(
    *,
    explicit_base_url: str | None,
    env_name: str,
    default_base_url: str,
) -> str:
    configured_base_url = explicit_base_url
    if configured_base_url is None:
        configured_base_url = os.getenv(env_name)
    candidate = configured_base_url if configured_base_url else default_base_url
    return validate_downstream_base_url(candidate, setting_name=env_name)


def validate_downstream_base_url(base_url: str, *, setting_name: str) -> str:
    """Validate an upstream URL without exposing its potentially sensitive value."""
    parsed, parsed_port = _parse_base_url(base_url, setting_name=setting_name)
    _validate_scheme(parsed, setting_name=setting_name)
    _validate_network_location(parsed, parsed_port=parsed_port, setting_name=setting_name)
    _validate_suffix(base_url, parsed=parsed, setting_name=setting_name)
    return base_url.rstrip("/")


def _parse_base_url(base_url: str, *, setting_name: str) -> tuple[SplitResult, int | None]:
    try:
        parsed = urlsplit(base_url)
        return parsed, parsed.port
    except ValueError as exc:
        raise ValueError(f"{setting_name} must be a valid downstream base URL") from exc


def _validate_scheme(parsed: SplitResult, *, setting_name: str) -> None:
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        _raise_invalid(setting_name, "must use http or https")


def _validate_network_location(
    parsed: SplitResult,
    *,
    parsed_port: int | None,
    setting_name: str,
) -> None:
    if parsed.hostname is None:
        _raise_invalid(setting_name, "must include a valid host and optional port")
    if parsed.username is not None or parsed.password is not None:
        _raise_invalid(setting_name, "must not include credentials")
    if (parsed_port is None and parsed.netloc.endswith(":")) or parsed_port == 0:
        _raise_invalid(setting_name, "must include a valid host and optional port")


def _validate_suffix(base_url: str, *, parsed: SplitResult, setting_name: str) -> None:
    if parsed.query or parsed.fragment or "?" in base_url or "#" in base_url:
        _raise_invalid(setting_name, "must not include a query string or fragment")
    if any(character.isspace() for character in base_url):
        _raise_invalid(setting_name, "must not include whitespace or control characters")


def _raise_invalid(setting_name: str, requirement: str) -> NoReturn:
    raise ValueError(f"{setting_name} {requirement}")
