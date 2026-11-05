"""Compatibility evaluation of an analysed E32 image against a device profile.

Verdicts: ``compatible`` | ``incompatible`` | ``unknown`` | ``not-tested``.

* ``incompatible``  - a static fact contradicts the profile (wrong kernel/CPU, corrupt header,
                      imported DLL absent from the supplied firmware profile, ...).
* ``compatible``    - ONLY when a user-supplied firmware profile resolves every import and all
                      static facts agree. It is still a *static* statement: runtime behaviour is
                      always reported as ``not-tested`` here.
* ``unknown``       - evidence is missing (typically: no firmware profile, so imports/APIs cannot
                      be resolved). Absence of information is never reported as compatibility.
* ``not-tested``    - nothing could be evaluated.
"""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from symport.devices.profiles import Profile
from symport.report import FAIL, FIRMWARE, PASS, STATIC, UNKNOWN, WARN, Report
from symport.theme import uids

ARM_RANK = {"armv4": 4, "armv5": 5, "armv6": 6}


class FirmwareProfileError(Exception):
    pass


@dataclass
class FirmwareProfile:
    id: str
    device: str
    firmware_version: str
    source: str
    dlls: dict[str, set[int] | None] = field(default_factory=dict)   # name -> ordinals (None = unknown)

    def has_dll(self, name: str) -> bool:
        return name.lower() in self.dlls

    def has_ordinals(self, name: str, ordinals: list[int]) -> tuple[bool, list[int]]:
        have = self.dlls.get(name.lower())
        if have is None:
            return True, []
        missing = sorted(set(ordinals) - have)
        return not missing, missing


def load_firmware_profile(path: Path) -> FirmwareProfile:
    """Load a user-supplied firmware profile (JSON or TOML). SymPort ships none: ROM images are
    not redistributable; generate it from your own firmware dump."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = tomllib.loads(text) if str(path).endswith(".toml") else json.loads(text)
    except (OSError, ValueError) as e:
        raise FirmwareProfileError(f"{path}: {e}") from e
    if data.get("schema") != 1 or "dlls" not in data:
        raise FirmwareProfileError(f"{path}: expected schema=1 and a 'dlls' table")
    for key in ("id", "device", "source"):
        if not data.get(key):
            raise FirmwareProfileError(f"{path}: missing '{key}'")
    dlls: dict[str, set[int] | None] = {}
    for name, v in data["dlls"].items():
        ords = v.get("ordinals") if isinstance(v, dict) else None
        dlls[name.lower()] = None if ords is None else {int(o) for o in ords}
    return FirmwareProfile(data["id"], data["device"], str(data.get("firmware_version", "")),
                           data["source"], dlls)


def evaluate(info: dict, profile: Profile, firmware: FirmwareProfile | None, rep: Report) -> str:
    """Add checks to ``rep`` and return the verdict string."""
    unknown = False
    failed = False

    def add(id: str, status: str, msg: str, level: str = STATIC, **ev) -> None:
        nonlocal unknown, failed
        rep.add(id, status, msg, level, **ev)
        failed |= status == FAIL
        unknown |= status == UNKNOWN

    add("e32.identity", PASS if info["uid_checksum_ok"] else FAIL,
        "UID checksum valid" if info["uid_checksum_ok"] else "UID checksum invalid (corrupt header)")
    crc = info["header_crc_ok"]
    add("e32.header_crc", PASS if crc else (UNKNOWN if crc is None else FAIL),
        {True: "header CRC valid", None: "header CRC not evaluated", False: "header CRC mismatch"}[crc])

    want_kernel = profile.value("platform.kernel")
    k = info["kernel"]
    if k.startswith("unknown") or not want_kernel:
        add("e32.kernel", UNKNOWN, f"kernel type {k}; profile kernel {want_kernel}")
    else:
        add("e32.kernel", PASS if k == want_kernel else FAIL,
            f"image targets {k}; profile {profile.id} is {want_kernel}"
            f" (profile fact status: {profile.fact('platform.kernel')['status']})")

    abi = profile.value("cpu.target_abi")
    cpu = info["cpu"]
    if cpu not in ARM_RANK or abi not in ARM_RANK:
        add("e32.cpu", UNKNOWN if cpu.startswith("unknown") else FAIL,
            f"image CPU {cpu}; profile ABI {abi}")
    elif ARM_RANK[cpu] > ARM_RANK[abi]:
        add("e32.cpu", FAIL, f"image needs {cpu} but the profile target ABI is {abi}")
    else:
        add("e32.cpu", PASS, f"image CPU {cpu} <= profile target ABI {abi}")

    if info["header_format"] == "V":
        add("e32.header_format", PASS, "V header (Symbian 9.x platform-security header)")
    else:
        add("e32.header_format", UNKNOWN, f"header format {info['header_format']}; "
            "Symbian 9.x image formats beyond 'V' are not evaluated")

    if info["abi"] == "eabi":
        add("e32.abi", PASS, "ARM EABI (Symbian 9.x toolchain ABI)")
    else:
        add("e32.abi", UNKNOWN, f"ABI {info['abi']}")

    caps = info.get("capabilities")
    if caps is None:
        add("e32.capabilities", UNKNOWN, "capabilities not available (non-V header)")
    else:
        restricted = info["restricted_capabilities"]
        add("e32.capabilities", WARN if restricted else PASS,
            "no capabilities" if not caps else
            ("capabilities: " + ", ".join(caps)
             + (f"; NOT user-grantable (need a certificate trusted by the phone): {', '.join(restricted)}"
                if restricted else "; all user-grantable on self-signed installs")),
            capabilities=caps)
    sid = info.get("secure_id")
    if sid:
        cls = uids.classify(int(sid, 16))
        add("e32.uid", WARN if cls != "test" else PASS,
            f"secure ID {sid} class {cls}: {uids.collision_note(int(sid, 16))}")

    imports = info.get("imports")
    if imports is None:
        add("e32.imports", UNKNOWN, info.get("imports_note") or "imports not decoded")
    elif not imports:
        add("e32.imports", PASS, "image imports no DLLs")
    elif firmware is None:
        names = sorted({i["name"] for i in imports})
        by_ord = sum(len(i["ordinals"]) for i in imports)
        add("e32.imports", UNKNOWN,
            f"imports {by_ord} ordinals from {len(names)} DLLs ({', '.join(names)}); no firmware "
            "profile supplied, so DLL/ordinal availability on this device is unknown",
            level=FIRMWARE, dlls=names)
    else:
        missing_dll, missing_ord = [], {}
        for i in imports:
            if not firmware.has_dll(i["name"]):
                missing_dll.append(i["name"])
                continue
            ok, miss = firmware.has_ordinals(i["name"], i["ordinals"])
            if not ok:
                missing_ord[i["name"]] = miss
        if missing_dll or missing_ord:
            add("e32.imports", FAIL, f"not present in firmware profile '{firmware.id}': "
                f"DLLs {missing_dll}; missing ordinals {missing_ord}", level=FIRMWARE)
        else:
            known_ord = all(firmware.dlls.get(i["name"]) is not None for i in imports)
            add("e32.imports", PASS if known_ord else WARN,
                f"all imported DLLs exist in firmware profile '{firmware.id}'"
                + ("" if known_ord else "; ordinal tables not available for some DLLs, so ordinals unchecked"),
                level=FIRMWARE)
    if failed:
        verdict = "incompatible"
    elif unknown:
        verdict = "unknown"
    else:
        verdict = "compatible"
    rep.add("compat.runtime", UNKNOWN, "runtime behaviour on firmware/emulator/device: not tested",
            level=FIRMWARE)
    rep.data["compatibility"] = {
        "target": profile.id, "status": verdict,
        "firmware_profile": firmware.id if firmware else None,
        "scope": "static only" + ("; imports checked against supplied firmware profile" if firmware else ""),
        "runtime": "not-tested",
    }
    return verdict
