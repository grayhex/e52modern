"""``symport device list|info|stage``: physical-device helpers via ``symbian device`` (symbian-platform).

``stage`` copies a SIS to the phone (mounted volume or MTP) and verifies the transfer; it does NOT
install, launch, debug, screenshot or control the phone, and nothing here flashes firmware or
erases data.
"""
from __future__ import annotations

from pathlib import Path

from symport.backends import modern_sdk
from symport.report import DEVICE, FAIL, PASS, UNKNOWN, WARN, Report
from symport.sis import reader
from symport.sis.fields import SisFormatError
from symport.util import sha256_file


def _sdk(rep: Report) -> modern_sdk.ModernSdk | None:
    sdk = modern_sdk.locate()
    if not sdk.available:
        rep.add("backend.symbian", FAIL, "symbian CLI (symbian-platform) not found", "environment")
        rep.unsupported("Device discovery/staging is provided by symbian-platform; not bundled.",
                        modern_sdk.INSTALL_HINT)
        return None
    return sdk


def device_list() -> Report:
    rep = Report("device list")
    sdk = _sdk(rep)
    if sdk:
        r, parsed = sdk.json(["device", "list"], timeout=60)
        rep.add("symbian.device.list", PASS if r.ok else FAIL, modern_sdk.summarize(r, parsed), DEVICE)
        rep.data["output"] = r.output
        if parsed:
            rep.data["sdk_result"] = parsed.get("result")
    rep.limitations.append("A USB product name or a successful file copy does not prove which firmware "
                           "the phone runs or that an application will execute.")
    return rep


def device_info(selector: str | None) -> Report:
    rep = Report("device info")
    sdk = _sdk(rep)
    if sdk:
        args = ["device", "info"] + (["--device", selector] if selector else [])
        r, parsed = sdk.json(args, timeout=60)
        rep.add("symbian.device.info", PASS if r.ok else FAIL, modern_sdk.summarize(r, parsed), DEVICE)
        rep.data["output"] = r.output
        if parsed:
            rep.data["sdk_result"] = parsed.get("result")
    return rep


def device_stage(sis: Path, selector: str | None) -> Report:
    rep = Report(f"device stage {Path(sis).name}")
    try:
        data = Path(sis).read_bytes()
        info = reader.inspect(data)
    except (OSError, SisFormatError) as e:
        rep.add("sis.valid", FAIL, f"refusing to stage an unreadable/invalid SIS: {e}")
        return rep
    ok = info["controller_crc_ok"] and info["data_crc_ok"] and info["uid_checksum_ok"]
    rep.add("sis.valid", PASS if ok else FAIL, "SIS structure verified before staging")
    if not ok:
        return rep
    rep.add("sis.signed", PASS if info["signed"] else WARN,
            "package is signed" if info["signed"] else "package is UNSIGNED: the phone may refuse it")
    sdk = _sdk(rep)
    if not sdk:
        return rep
    args = ["device", "install", "--package", str(sis)] + (["--device", selector] if selector else [])
    r, parsed = sdk.json(args, timeout=600)
    rep.add("symbian.device.stage", PASS if r.ok else FAIL, modern_sdk.summarize(r, parsed), DEVICE,
            sha256=sha256_file(Path(sis)))
    rep.add("device.install", UNKNOWN, "staged only: finish installation on the handset and record the "
            "result with the manual checklist (docs/DEVICE_TEST.md)", DEVICE)
    rep.verification["physical_device"] = "staged-not-installed" if r.ok else "failed"
    rep.limitations += ["No automated installation, launch confirmation, screenshots or TRK debugging."]
    return rep
