"""Fixed, privacy-safe reasons why a phone connection did not answer.

Raw Gammu/OS text is never forwarded: it is matched against known codes/phrases and replaced by
one of the reasons below, which the UI maps to a concrete fix. Best effort: phrases come from
Gammu's documented error table and are not exercised against a physical Nokia E52.
"""

from __future__ import annotations

import re

REASONS = (
    "port-busy",  # another program (Nokia Suite, a second Gammu) holds the COM port
    "port-open",  # cannot be opened: unknown, busy or no permission
    "port-missing",  # configured port does not exist (cable unplugged, wrong COM number)
    "port-permission",
    "driver-missing",  # no driver for the device
    "no-response",  # port opens, the phone does not answer (wrong USB mode, locked phone)
    "not-connected",
    "gammu-missing",  # neither python-gammu nor the gammu executable is available
    "config-invalid",
    "unsupported-model",  # answered, but not a supported Nokia S60 3rd/5th Edition model
    "unknown",
)

CODES = {
    "ERR_DEVICELOCKED": "port-busy",
    "ERR_DEVICEBUSY": "port-busy",
    "ERR_DEVICEOPENERROR": "port-open",
    "ERR_DEVICENOTEXIST": "port-missing",
    "ERR_DEVICENOPERMISSION": "port-permission",
    "ERR_DEVICENODRIVER": "driver-missing",
    "ERR_TIMEOUT": "no-response",
    "ERR_NOTCONNECTED": "not-connected",
    "ERR_DEVICEREADERROR": "no-response",
    "ERR_DEVICEWRITEERROR": "no-response",
    "ERR_CANTOPENFILE": "config-invalid",
    "ERR_USING_DEFAULTS": "config-invalid",
    "ERR_UNCONFIGURED": "config-invalid",
}
PHRASES = (
    (r"unknown, busy or no permission", "port-open"),
    (r"it is locked|already in use|in use by other", "port-busy"),
    (r"doesn.t exist|does not exist|no such file", "port-missing"),
    (r"permission", "port-permission"),
    (r"no required driver|no driver", "driver-missing"),
    (r"no response|timeout|not connected", "no-response"),
    (r"error opening device|can.t open device", "port-open"),
    (r"config", "config-invalid"),
)


def classify(text: object) -> str:
    """Map an adapter/CLI error text to one reason; unknown text becomes ``unknown``."""
    value = str(text or "")
    for code in re.findall(r"ERR_[A-Z_]+", value):
        if code in CODES:
            return CODES[code]
    for pattern, reason in PHRASES:
        if re.search(pattern, value, re.IGNORECASE):
            return reason
    return "unknown"
