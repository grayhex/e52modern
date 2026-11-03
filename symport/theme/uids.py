"""UID range classification and known-UID collision checks for skin packages."""
from __future__ import annotations

# Skin UIDs seen in the public Nokia sources (SymbianSource/oss.FCL.sf.mw.uiresources,
# skins/AknSkinContent) — a *small* denylist, not a registry of all packages in the world.
KNOWN_SKIN_UIDS = {
    0x101F84B9: "Series 60 default scalable skin (scalableseries60skin)",
    0x2000B12D: "Nokia 'Haze' skin",
    0x2000B12E: "Nokia 'Jing' skin",
}

TEST_RANGE = (0xE0000000, 0xEFFFFFFF)
UNPROTECTED_RANGE = (0xA0000000, 0xBFFFFFFF)
PROTECTED_RANGE = (0x00000000, 0x7FFFFFFF)


def classify(uid: int) -> str:
    if TEST_RANGE[0] <= uid <= TEST_RANGE[1]:
        return "test"
    if UNPROTECTED_RANGE[0] <= uid <= UNPROTECTED_RANGE[1]:
        return "unprotected"
    if PROTECTED_RANGE[0] <= uid <= PROTECTED_RANGE[1]:
        return "protected"
    return "other"


def collision_note(uid: int) -> str:
    cls = classify(uid)
    if uid in KNOWN_SKIN_UIDS:
        return f"collides with {KNOWN_SKIN_UIDS[uid]}"
    if cls == "test":
        return ("test range: shared by every developer's experiments (28 bits of space), so a "
                "collision with a foreign package is possible but unlikely; pick a random UID of "
                "your own and never publish a package with a test-range UID")
    if cls == "protected":
        return "protected range: needs a UID allocated by Symbian Signed; a self-signed package will be rejected"
    if cls == "unprotected":
        return "unprotected range: needs a UID allocated via Symbian Signed to avoid collisions"
    return "UID range not recognised"
