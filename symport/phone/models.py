"""Documented Nokia S60 model families; never measured firmware or OS versions."""

import json
import re
from pathlib import Path

S60_MODELS = {
    "E51": "3rd FP1",
    "E52": "3rd FP2",
    "E55": "3rd FP2",
    "E61": "3rd",
    "E61I": "3rd",
    "E63": "3rd FP1",
    "E65": "3rd",
    "E66": "3rd FP1",
    "E71": "3rd FP1",
    "E72": "3rd FP2",
    "E75": "3rd FP2",
    "E90": "3rd FP1",
    "N73": "3rd",
    "N78": "3rd FP2",
    "N79": "3rd FP2",
    "N81": "3rd FP1",
    "N82": "3rd FP1",
    "N85": "3rd FP2",
    "N86": "3rd FP2",
    "N95": "3rd FP1",
    "N96": "3rd FP2",
    "N97": "5th",
    "5230": "5th",
    "5530": "5th",
    "5800": "5th",
    "C5-03": "5th",
    "X6": "5th",
    "C6-00": "5th",
}


def documented_model(value: str) -> dict | None:
    for model, edition in S60_MODELS.items():
        if re.search(r"(?<![A-Z0-9])" + re.escape(model) + r"(?![A-Z0-9])", value.upper()):
            return {
                "manufacturer": "Nokia",
                "model": model,
                "s60": edition,
                "edition": "5th" if edition == "5th" else "3rd",
                "source": "documented-model-profile",
                "measured": False,
            }
    return None


# Symbian OS release implied by the documented S60 edition (S60 3rd Edition ... 5th Edition).
SYMBIAN_BY_EDITION = {"3rd": "9.1", "3rd FP1": "9.2", "3rd FP2": "9.3", "5th": "9.4"}
REGISTRY_FILE = Path(__file__).with_name("device_models.json")
_FIELDS = {"id", "model", "name", "family", "image", "screen", "input", "toolchain_profile", "source", "name_ru", "artwork", "s60", "symbian", "storage", "platform_uids", "profile", "rms", "aliases", "fact_status", "measured", "hardware", "selectable", "target_model"}


def load_registry(path: Path | None = None) -> list[dict]:
    """Phone models with artwork/geometry. Strict: a bad entry fails loudly, never half-loads."""
    document = json.loads((path or REGISTRY_FILE).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != 1:
        raise ValueError("Unsupported device model registry")
    seen, result = set(), []
    for entry in document.get("models", []):
        if not isinstance(entry, dict) or set(entry) - _FIELDS - {"_comment"}:
            raise ValueError("Invalid device model entry")
        if not re.fullmatch(r"nokia-[a-z0-9-]{2,30}", str(entry.get("id", ""))) or entry["id"] in seen:
            raise ValueError("Invalid or duplicate model id")
        if str(entry.get("model", "")).upper() not in S60_MODELS:
            raise ValueError("Add the model to S60_MODELS (documented edition) first")
        image, screen = entry.get("image"), entry.get("screen")
        if image is not None and not re.fullmatch(r"/phones/[a-z0-9-]+\.(?:png|webp|svg)", str(image)):
            raise ValueError("Invalid model image path")
        if screen is not None and (
            set(screen) != {"width", "height", "orientation"}
            or not all(type(screen[k]) is int and 64 <= screen[k] <= 2048 for k in ("width", "height"))
            or screen["orientation"] not in ("portrait", "landscape")
        ):
            raise ValueError("Invalid model screen")
        seen.add(entry["id"])
        result.append({k: v for k, v in entry.items() if k != "_comment"})
    return result


def _documented_profile(model: dict) -> dict:
    edition = S60_MODELS[model["model"].upper()]
    return {"s60": edition, "symbian": SYMBIAN_BY_EDITION.get(edition)}


def catalog() -> list[dict]:
    """Registry entries completed with documented platform facts, for UI selectors."""
    return [
        {**entry, **_documented_profile(entry), "source": entry.get("source") or "documented-model-profile"}
        for entry in load_registry()
    ]


def presentation(value: str, *, rm=None, product_code=None) -> dict | None:
    """Model identity from the adapter response; geometry/artwork come from the registry.

    A documented S60 model without a registry entry still gets a profile (name, edition) but no
    artwork or geometry: the UI then shows a labelled generic illustration instead of guessing.
    """
    from .registry import identify
    resolved = identify(value, rm=rm, product_code=product_code)
    if resolved:
        return resolved
    model = documented_model(value)
    if not model:
        return None
    entry = next((e for e in catalog() if e["model"].upper() == model["model"]), None)
    if entry:
        return {
            "id": entry["id"],
            "name": entry["name"],
            "image": entry["image"],
            "screen": entry["screen"],
            "s60": entry["s60"],
            "symbian": entry["symbian"],
            "input": entry["input"],
            "source": "documented-model-profile",
        }
    edition = S60_MODELS[model["model"]]
    return {
        "id": "nokia-" + re.sub(r"[^a-z0-9]+", "-", model["model"].lower()).strip("-"),
        "name": "Nokia " + model["model"],
        "image": None,
        "screen": None,
        "s60": edition,
        "symbian": SYMBIAN_BY_EDITION.get(edition),
        "input": None,
        "source": "documented-model-profile",
    }
