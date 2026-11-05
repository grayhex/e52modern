"""Single documented presentation/platform registry; never a capability or telemetry source."""

from __future__ import annotations

import copy
import re


def registry():
    from .models import catalog

    return {
        p["id"]: dict(
            p,
            selectable=p.get("selectable", bool(p.get("toolchain_profile"))),
            aliases=p.get("aliases", [p["model"]]),
            rms=p.get("rms", []),
            platform_uids=p.get("platform_uids", []),
        )
        for p in catalog()
    }


def selectable_profiles():
    return {key: copy.deepcopy(p) for key, p in registry().items() if p["selectable"]}


def name_matches(value, alias, *, exact=False):
    value = re.sub(r"\s*-\s*", "-", str(value or "").upper())
    alias = re.escape(alias.upper()).replace(r"\ ", r"\s*")
    suffix = r"(?![A-Z0-9-])" if exact else r"(?![A-Z0-9])"
    return bool(re.search(r"(?<![A-Z0-9])" + alias + suffix, value))


def theme_profiles():
    return {
        key: p
        for key, p in selectable_profiles().items()
        if p.get("theme_studio", {}).get("status") == "supported"
    }


def identify(value: str, *, rm=None, product_code=None):
    """Resolve only explicit model variants or documented RM evidence; bare N95 stays ambiguous.

    Product codes are preserved only as observations. No unverified product-code lookup is shipped.
    Conflicting model/RM evidence downgrades to the common family, never a guessed variant.
    """
    value = value if isinstance(value, str) else ""
    upper = value.upper()
    is_n95 = bool(re.search(r"(?<![A-Z0-9])N95(?![A-Z0-9])", upper))
    observed_rm = set(re.findall(r"\bRM-\d+\b", upper + " " + str(rm or "").upper()))
    candidates, names, codes = set(), set(), set()
    for key, p in registry().items():
        for alias in p["aliases"]:
            if name_matches(upper, alias, exact=p.get("exact_aliases", False)):
                candidates.add(key)
                names.add(key)
        if observed_rm.intersection(p["rms"]):
            candidates.add(key)
            codes.add(key)
    n95_candidates = {c for c in candidates if c.startswith("nokia-n95")}
    # "N95" alone intentionally is not an alias for a physical variant.
    family = is_n95 or bool(n95_candidates)
    if len(candidates) == 1:
        key = next(iter(candidates))
        # An unknown RM on an identified N95 is conflicting evidence, not confirmation.
        if family and observed_rm and not observed_rm.issubset(set(registry()[key]["rms"])):
            key = "nokia-n95-family"
    elif family and all(c.startswith("nokia-n95") for c in candidates):
        key = "nokia-n95-family"
    else:
        return None
    result = copy.deepcopy(registry()[key])
    result["profile_source"] = result["source"]
    result["source"] = "documented-model-profile"
    result["identity_basis"] = (
        "ambiguous"
        if key == "nokia-n95-family"
        else "reported-model-and-rm"
        if key in names and key in codes
        else "reported-rm"
        if key in codes
        else "reported-model"
    )
    result["variant_known"] = key != "nokia-n95-family"
    result["identity_note"] = (
        "Read the model suffix or RM to identify the N95 variant; storage size is not an identity probe"
        if not result["variant_known"]
        else None
    )
    result.pop("rms", None)
    result.pop("aliases", None)
    return result


def target_profile(target):
    target = target if isinstance(target, dict) else {}
    return identify(
        target.get("model", ""), rm=target.get("rm"), product_code=target.get("product_code")
    )


def collection_profiles():
    return {
        key: {
            "model": p["name"],
            "symbian": p["symbian"],
            "s60": p["s60"],
            "screen": [p["screen"]["width"], p["screen"]["height"]],
        }
        for key, p in selectable_profiles().items()
    }
