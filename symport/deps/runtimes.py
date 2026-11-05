"""Knowledge tables for package dependency analysis.

Everything here is *static knowledge about names and IDs*; none of it says what is installed on a
phone. Each entry carries a ``source`` so a reader can tell documentation from heuristics.
"""
from __future__ import annotations

import re

from symport.phone.registry import registry

# Platform ("S60ProductID" / "Series60ProductID") dependency UIDs. ``rank`` orders releases inside
# one family; product IDs are compared with the selected documented device profile.
PLATFORMS: dict[int, dict] = {
    0x101F7961: {"name": "S60 3rd Edition", "symbian": "9.1", "family": "s60-3rd", "rank": 0,
                 "source": "profiles/nokia-e52.toml packaging.platform_dependency (documented)"},
    0x102032BE: {"name": "S60 3rd Edition FP1", "symbian": "9.2", "family": "s60-3rd", "rank": 1,
                 "source": "jellyfin-s60v3 klient/klient.pro comments (Symbian 9.2)"},
    0x102752AE: {"name": "S60 3rd Edition FP2", "symbian": "9.3", "family": "s60-3rd", "rank": 2,
                 "source": "jellyfin-s60v3 klient/klient.pro comments (Symbian 9.3)"},
    0x1028315F: {"name": "S60 5th Edition / Symbian^1", "symbian": "9.4", "family": "s60-5th", "rank": 3,
                 "source": "jellyfin-s60v3 klient/klient.pro comments (Symbian^1)"},
    0x20022E6D: {"name": "Symbian^3", "symbian": "^3", "family": "symbian3", "rank": 4,
                 "source": "jellyfin-s60v3 klient/klient.pro comments (Symbian^3)"},
    0x2003A678: {"name": "Symbian Belle", "symbian": "Belle", "family": "symbian3", "rank": 5,
                 "source": "jellyfin-s60v3 klient/klient.pro comments (Symbian Belle)"},
}

# Static product-family candidates, never an installed product-package/version attestation.
# Earlier 3rd Edition UIDs on later handsets are inferred from package practice; the device's
# native documented product UID is marked separately. Firmware version constraints stay unknown.
DEVICE_PLATFORMS = {
    key: {uid: ("documented" if uid == p.get('native_platform_uid') else "inferred") for uid in p['platform_uids']}
    for key,p in registry().items()
}


PLATFORM_NAMES = re.compile(r"^(s60|series60)productid$", re.I)

# Runtime families recognised from declared dependency names and from imported DLL names.
RUNTIMES: dict[str, dict] = {
    "qt": {
        "title": "Qt for Symbian",
        "names": re.compile(r"^qt$", re.I),
        "imports": re.compile(r"^(qt(core|gui|network|xml|xmlpatterns|svg|sql|script|scripttools|webkit|opengl|test|"
                              r"declarative|multimedia|help|clucene)|phonon)$", re.I),
        "uids": {0x2001E61C: "observed as the dependency named 'Qt' in jellyfin-s60v3 0.3.22"},
        "distribution": "Not distributed by SymPort. A matching Qt runtime package must be supplied and "
                        "installed before the application.",
    },
    "qt-mobility": {
        "title": "Qt Mobility",
        "names": re.compile(r"^qt ?mobility", re.I),
        "imports": re.compile(r"^qt(serviceframework|servicefw|contacts|location|multimediakit|sensors|messaging|"
                              r"systeminfo|versit|versitorganizer|connectivity|feedback|gallery|organizer|"
                              r"publishsubscribe|bearer|mobility\w*)$", re.I),
        "uids": {},
        "distribution": "Not distributed by SymPort. Qt Mobility is a separate runtime package.",
    },
    "pys60": {
        "title": "Python for S60 (PyS60)",
        "names": re.compile(r"^(python|pys60)", re.I),
        "imports": re.compile(r"^python\d*(_\w+)?$", re.I),
        "uids": {},
        "distribution": "Not distributed by SymPort. The Python runtime is a separate package matching the script version.",
    },
    "open-c": {
        "title": "Open C / P.I.P.S.",
        "names": re.compile(r"^(open ?c|pips|p\.i\.p\.s)", re.I),
        "imports": re.compile(r"^(libc|libm|libpthread|libdl|libz|libcrypt|libssl|libcrypto|libglib\w*|libgobject\w*|"
                              r"libstdcpp\w*|stdcpp\w*|libpthread\w*)$", re.I),
        "uids": {},
        "distribution": "Not distributed by SymPort. Open C/C++ is a separate runtime package.",
    },
}


def platform(uid: int | None) -> dict | None:
    return None if uid is None else PLATFORMS.get(uid)


def runtime_for_name(name: str) -> str | None:
    """Runtime family for a *declared dependency name*; ``None`` when unknown."""
    for key, spec in RUNTIMES.items():
        if spec["names"].search(name.strip()):
            return key
    return None


def runtime_for_uid(uid: int | None) -> str | None:
    for key, spec in RUNTIMES.items():
        if uid in spec["uids"]:
            return key
    return None


def runtime_for_import(dll: str) -> str | None:
    """Runtime family for an imported DLL file name (version/UID decorations are ignored)."""
    stem = re.sub(r"\{[0-9a-fA-F]{8}\}|\[[0-9a-fA-F]{8}\]", "", dll)
    stem = stem.rsplit(".", 1)[0].strip().lower()
    for key, spec in RUNTIMES.items():
        if spec["imports"].fullmatch(stem):
            return key
    return None
