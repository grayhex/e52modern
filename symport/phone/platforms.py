"""Release evidence for upgradeable Symbian^3 handsets; model identity is not an OS probe."""

from __future__ import annotations

RELEASES = ("^3", "Anna", "Belle", "Belle Refresh")


def release(value):
    aliases = {
        "^3": "^3",
        "symbian^3": "^3",
        "anna": "Anna",
        "symbian anna": "Anna",
        "belle": "Belle",
        "nokia belle": "Belle",
        "symbian belle": "Belle",
        "belle refresh": "Belle Refresh",
        "nokia belle refresh": "Belle Refresh",
    }
    return aliases.get(str(value or "").strip().casefold())


def platform_state(profile, target_os=""):
    """Return accepted product IDs, uncertain IDs and any explicit OS mismatch."""
    accepted = {
        u: "documented" if u == profile.get("native_platform_uid") else "inferred"
        for u in profile.get("platform_uids", [])
    }
    if profile.get("platform_family") != "symbian3":
        return (
            accepted,
            set(),
            bool(target_os and profile.get("symbian") and target_os != profile["symbian"]),
        )
    current = release(target_os)
    if current in ("Belle", "Belle Refresh"):
        accepted[0x2003A678] = "explicit-target-release; not a device probe"
    uncertain = {0x2003A678} if not target_os else set()
    return accepted, uncertain, bool(target_os and current is None)
