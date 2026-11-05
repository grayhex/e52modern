"""Model-specific evidence without promoting legacy E52 claims to other Nokia models."""

from __future__ import annotations

import copy
import re

from symport.phone.registry import selectable_profiles


def evidence(entry):
    result = {}
    for key, profile in selectable_profiles().items():
        explicit = copy.deepcopy(entry.get("model_evidence", {}).get(key, {}))
        status = explicit.get("status", "not-tested")
        sources = explicit.get("sources", [])
        reason = explicit.get("reason", "No test report for this model and package build")
        basis = "model-test" if status == "verified" else "not-tested"
        if key == "nokia-e52" and not explicit:
            status = (
                "verified"
                if entry["compatibility"] == "verified-on-e52" and entry.get("e52_evidence")
                else "not-tested"
            )
            sources = entry.get("e52_evidence") or []
            reason = entry.get("compatibility_basis", reason)
            basis = "legacy-e52-evidence"
        platforms = " ".join(entry["platforms"]).lower()
        minimum = entry.get("minimum_symbian")
        minimum_match = re.fullmatch(r"9\.([1-4])", minimum or "")
        minimum_os_blocked = minimum_match and float(minimum) > float(profile["symbian"])
        fp2_only = (
            ("fp2" in platforms or "feature pack 2" in platforms)
            and "fp1" not in platforms
            and profile["symbian"] == "9.2"
        )
        if (
            minimum_os_blocked
            or fp2_only
            or entry.get("target_profiles")
            and key not in entry["target_profiles"]
        ):
            status, basis, reason = (
                "unsupported",
                "declared-platform",
                "The declared OS/platform or target profile excludes this model",
            )
        if entry["compatibility"] in ("unsupported", "unavailable"):
            status, basis, reason = (
                entry["compatibility"],
                "distribution",
                "No supported distribution in the catalog",
            )
        result[key] = {
            "status": status,
            "basis": basis,
            "reason": reason,
            "sources": sources,
            "platform": profile["s60"],
            "symbian": profile["symbian"],
            "package_sha256": explicit.get("package_sha256"),
            "version": entry["version"],
            "installation": "not-tested" if status != "verified" else "reported-by-source",
        }
    return result


def assessment(entry, profile):
    return evidence(entry).get(
        profile,
        {
            "status": "not-tested",
            "basis": "unknown-model",
            "reason": "Select an exact model variant",
        },
    )


def platform_evidence(entry):
    """Declared platform metadata is separate from physical installation evidence."""
    models = evidence(entry)
    return {
        key: {
            "status": "unsupported"
            if all(models[m]["status"] == "unsupported" for m in ids)
            else "not-tested",
            "declared": list(entry["platforms"]),
            "sources": list(entry["sources"]),
            "basis": "catalog-platform-metadata; not a binary or hardware test",
        }
        for key, ids in {
            "s60-3rd-fp1": ("nokia-n95", "nokia-n95-8gb"),
            "s60-3rd-fp2": ("nokia-e52", "nokia-e72"),
        }.items()
    }
