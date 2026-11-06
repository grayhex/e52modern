"""Model-specific evidence without promoting legacy E52 claims to other Nokia models."""

from __future__ import annotations

import copy
import re

from symport.phone.registry import selectable_profiles


def _os_number(value):
    """Leading numeric part of a Symbian release ("9.2" -> 9.2, "7.0s" -> 7.0, "^3" -> None)."""
    found = re.match(r"\d+(?:\.\d+)?", str(value or ""))
    return float(found.group()) if found else None


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
        platform_number = _os_number(profile.get("symbian"))
        minimum_os_blocked = minimum_match and platform_number and float(minimum) > platform_number
        legacy_platform = profile.get("platform_family") == "s60v2"
        if minimum in ('^3', 'Anna', 'Belle', 'Belle Refresh'):
            minimum_os_blocked = profile.get('platform_family') != 'symbian3'
            if not minimum_os_blocked:
                status, basis, reason = 'not-tested', 'release-unverified', 'The installed OS release/runtime must be checked separately'
        legacy_only = (profile.get("platform_family") == "symbian3" and entry.get("format") in ("sis", "sisx")
                       and re.search(r's60\s*(?:3rd|5th)|fp[12]', platforms)
                       and not re.search(r'symbian\s*\^?3|anna|belle', platforms))
        fp2_only = (
            ("fp2" in platforms or "feature pack 2" in platforms)
            and "fp1" not in platforms
            and profile["symbian"] == "9.2"
        )
        if legacy_platform and status != "unsupported":
            # S60 2nd Edition: nothing here is verified for it, so never "compatible".
            status, basis, reason = (
                "not-tested",
                "legacy-platform-not-assessed",
                "S60 2nd Edition (Symbian 7.0s) is an older platform; SymPort has no verified rules for it",
            )
        if (
            minimum_os_blocked
            or legacy_only
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
            "s60-5th": ("nokia-n97-mini",),
            "s60-2nd": ("nokia-7610",),
            "symbian3": ("nokia-n8", "nokia-e7"),
        }.items()
    }
