"""Read-only model-level firmware comparison. This is not an image/flash manifest."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def reference() -> dict:
    return json.loads(
        Path(__file__).with_name("firmware_reference.json").read_text(encoding="utf-8")
    )


def version(value) -> tuple[int, ...] | None:
    if not isinstance(value, str):
        return None
    matches = re.findall(r"(?<![\d.])(\d{1,3}\.\d{1,3}(?:\.\d{1,3})?)(?![\d.])", value)
    if len(matches) != 1:
        return None
    parts = tuple(int(p) for p in matches[0].split("."))
    return parts + (0,) * (3 - len(parts))


def assess(device: dict) -> dict:
    model = str(device.get("model") or "")
    matches = re.findall(r"\bE(?:52|72)\b", model, re.I)
    models = {m.upper() for m in matches}
    entry = next((x for x in reference()["models"] if models == {x["model"]}), None)
    result = {
        "status": "unknown",
        "model": entry["model"] if entry else None,
        "latest_known": entry["latest_known"] if entry else None,
        "sources": entry["sources"] if entry else [],
        "scope": "model-reference",
        "install_available": False,
        "variant_verified": False,
        "reviewed": reference()["reviewed"],
    }
    current = version(device.get("firmware"))
    if entry and current is not None:
        target = version(entry["latest_known"])
        result["status"] = (
            "older"
            if current < target
            else "current-in-reference"
            if current == target
            else "newer-than-reference"
        )
    return result
