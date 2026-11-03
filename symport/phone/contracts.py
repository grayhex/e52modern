"""Capability-based device access. Mounted volumes are never inferred to be phones.

Roots are explicitly enrolled by the operator, not accepted from HTTP clients.
No symlinks, recursive deletion, shell execution or implicit installation.
"""
from __future__ import annotations

from typing import Protocol

LIMIT = 8 * 1024 * 1024

class Transport(Protocol):
    def devices(self) -> list[dict]: ...
    def execute(self, data: dict) -> dict: ...


