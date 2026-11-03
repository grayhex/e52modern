"""Shared loopback/Origin/key policy for Python PC Bridge and packaged agent."""

from __future__ import annotations

import secrets
from urllib.parse import urlsplit


def host_allowed(host: str, port: int) -> bool:
    return host in (f"127.0.0.1:{port}", f"localhost:{port}")


def origin_allowed(origin: str | None, origins: set[str]) -> bool:
    if not origin:
        return True  # authenticated non-browser backend / SSH tunnel
    if origin not in origins:
        return False
    try:
        value = urlsplit(origin)
        return (
            value.scheme in ("http", "https")
            and not value.username
            and not value.password
            and not value.path
            and not value.query
            and not value.fragment
        )
    except ValueError:
        return False


def key_allowed(provided: str, expected: str) -> bool:
    return len(expected) >= 32 and secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    )
