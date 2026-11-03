"""``symport theme package``: turn a built skin (.skn/.mbm/.mif/.pkg) into a SIS package."""
from __future__ import annotations

import hashlib
from pathlib import Path

from symport.backends import modern_sdk, packaging
from symport.config import Config
from symport.report import DEVICE, FAIL, FIRMWARE, PASS, SKIP, UNKNOWN, WARN, Report
from symport.sis import reader
from symport.sis.fields import SisFormatError
from symport.sis.writer import build as build_sis
from symport.theme import inspect as tinspect
from symport.theme import pkgfile, uids
from symport.util import artifact_entry


def package_variant(cfg: Config, variant: str, backend: str | None = None,
                    output: Path | None = None, sign_cert: Path | None = None,
                    sign_key: Path | None = None) -> Report:
    rep = Report(f"theme package --variant {variant}")
    rep.verification["static_automated"] = True
    base = tinspect.find_base(cfg, variant)
    if base is None:
        rep.add("dist.present", FAIL, "no built skin: run `symport theme build` first")
        return rep
    pkg_path = base.with_suffix(".pkg")
    try:
        pkg = pkgfile.parse(pkg_path.read_text(encoding="ascii", errors="replace"))
    except pkgfile.PkgError as e:
        rep.add("pkg.parse", FAIL, str(e))
        return rep

    # --- pre-flight: the package must pass static inspection first
    pre = tinspect.inspect_variant(cfg, variant)
    failed = [c for c in pre.checks if c.status == FAIL]
    rep.add("preflight.inspect", FAIL if failed else PASS,
            "static inspection passed" if not failed else
            "static inspection failed: " + ", ".join(c.id for c in failed))
    if failed:
        return rep
    cls = uids.classify(pkg.uid)
    rep.add("uid.range", WARN if cls == "test" else PASS, f"UID {pkg.uid:#010x} class {cls}: "
            + uids.collision_note(pkg.uid))

    be = packaging.discover(cfg)
    chosen = backend or be.configured
    rep.data["backends"] = be.status()
    rep.data["capability_matrix"] = packaging.CAPABILITY_MATRIX
    out_dir = output or (cfg.build_dir / "theme" / variant)
    out_dir.mkdir(parents=True, exist_ok=True)
    unsigned = out_dir / f"{base.name}.sis"

    if chosen == "modern-sdk":
        rep.unsupported("symbian-platform's SIS writer packages E32 executables only; it cannot "
                        "install .skn/.mbm/.mif files, declare dependencies or use .pkg scripts.",
                        packaging.MAKESIS_HELP)
        return rep
    if chosen == "auto":
        chosen = "makesis" if be.makesis else "unavailable"
    if chosen == "unavailable":
        rep.add("backend.select", FAIL, "no suitable SIS packager found (makesis missing)")
        rep.unsupported("No official MakeSIS available and the experimental native writer was not "
                        "requested. No SIS was produced.", packaging.MAKESIS_HELP)
        return rep
    if chosen == "makesis":
        if not be.makesis:
            rep.add("backend.select", FAIL, "makesis requested but not found")
            rep.unsupported("makesis not found.", packaging.MAKESIS_HELP)
            return rep
        rep.add("backend.select", PASS, "official MakeSIS", backend="makesis", command=be.makesis,
                level="environment")
        if unsigned.exists():
            unsigned.unlink()
        r = packaging.run_makesis(be.makesis, pkg_path, unsigned)
        if not r.ok or not unsigned.is_file():
            rep.add("makesis.run", FAIL, f"makesis exited {r.returncode}: {r.output[:500]}")
            return rep
        rep.add("makesis.run", PASS, "makesis produced a package", level="environment")
        dropped: list[str] = []
        rep.limitations.append("SIS built by official MakeSIS; acceptance by the phone is still untested.")
    elif chosen == "native":
        rep.add("backend.select", WARN, "EXPERIMENTAL native writer selected explicitly",
                backend="native", level="environment")
        try:
            sp, dropped = packaging.to_sis_package(pkg, pkg_path.parent)
            unsigned.write_bytes(build_sis(sp))
            again = build_sis(sp)
            rep.add("native.deterministic", PASS if again == unsigned.read_bytes() else FAIL,
                    "rebuilding gives byte-identical output")
        except (SisFormatError, OSError) as e:
            rep.add("native.build", FAIL, str(e))
            return rep
        for d in dropped:
            rep.add("native.dropped", WARN, d)
        rep.limitations += [
            "EXPERIMENTAL: produced by symport's own writer, modelled on the symbian-platform "
            "reference implementation; never accepted by MakeSIS/SignSIS or a phone in this project.",
            "Dependencies and S60-version prerequisites are not encoded (see warnings).",
            "Package is unsigned; the phone's installation policy decides whether it can be installed.",
        ]
    else:
        rep.add("backend.select", FAIL, f"unknown backend {chosen!r} (use auto|makesis|native|modern-sdk)")
        return rep

    final = unsigned
    if sign_cert or sign_key:
        if not (sign_cert and sign_key):
            rep.add("sign.args", FAIL, "--cert and --key must be given together")
            return rep
        if not be.signsis:
            rep.add("sign.tool", FAIL, "signsis not found")
            rep.unsupported("Signing needs the official SignSIS (the native writer cannot sign).",
                            packaging.MAKESIS_HELP)
            return rep
        signed = out_dir / f"{base.name}.sisx"
        r = packaging.run_signsis(be.signsis, unsigned, signed, sign_cert, sign_key)
        if not r.ok or not signed.is_file():
            rep.add("sign.run", FAIL, f"signsis exited {r.returncode}: {r.output[:500]}")
            return rep
        rep.add("sign.run", PASS, "package signed (signature validity not verified by SymPort)",
                level="environment")
        rep.limitations.append("Signing does not grant trust on the phone; certificate acceptance "
                               "is decided by the E52 install policy.")
        final = signed
    else:
        rep.limitations.append("Package is UNSIGNED. Pass --cert/--key (official SignSIS) to sign.")

    # --- verify what was actually produced
    verify_sis(final, pkg, pkg_path.parent, rep)
    rep.artifacts.append(artifact_entry(final, cfg.repo))
    rep.add("firmware.install", UNKNOWN, "installation on E52 firmware not tested", level=FIRMWARE)
    rep.add("device.install", UNKNOWN, "no physical-device test recorded", level=DEVICE)
    rep.data["package"] = {"name": pkg.name, "uid": f"{pkg.uid:#010x}", "backend": chosen,
                           "signed": final.suffix == ".sisx"}
    return rep


def verify_sis(sis: Path, pkg: pkgfile.Pkg, src_dir: Path, rep: Report) -> None:
    """Independently re-read the produced SIS and compare with the .pkg and source files."""
    try:
        info = reader.inspect(sis.read_bytes())
    except SisFormatError as e:
        rep.add("sis.parse", FAIL, f"produced file is not a valid SIS: {e}")
        return
    rep.add("sis.checksums", PASS if (info["uid_checksum_ok"] and info["controller_crc_ok"]
                                       and info["data_crc_ok"]) else FAIL,
            "UID checksum and controller/data CRC16 verified")
    rep.add("sis.uid", PASS if info["package"]["uid"] == pkg.uid == info["uid3"] else FAIL,
            f"package UID {info['package']['uid']:#010x} matches .pkg")
    want = {e.dest.lower(): e for e in pkg.files if not e.options.upper().startswith("FN")}
    got = {f["target"].lower(): f for f in info["files"]}
    problems = []
    for dest, e in want.items():
        f = got.get(dest)
        if f is None:
            problems.append(f"missing {e.dest}")
            continue
        src = (src_dir / e.source).read_bytes()
        if f.get("hash_ok") is not True:
            problems.append(f"{e.dest}: embedded data hash/length mismatch")
        elif f["sha1"] != hashlib.sha1(src).hexdigest():
            problems.append(f"{e.dest}: content differs from {e.source}")
    extra = set(got) - set(want)
    if extra:
        problems.append(f"unexpected files in SIS: {sorted(extra)}")
    rep.add("sis.contents", FAIL if problems else PASS,
            f"{len(want)} files installed at the declared S60 skin paths, data matches sources"
            if not problems else "; ".join(problems), files=sorted(want))
    dep = info["dependencies"]
    if dep["declared"]:
        rep.add("sis.dependencies", PASS,
                f"{dep['declared']} dependency elements declared (UIDs, best effort: "
                f"{[hex(u) for u in dep['uids_best_effort']]})")
    else:
        rep.add("sis.dependencies", WARN,
                "package declares NO dependency elements (S60 version / skin support not checked by installer)")
    rep.add("sis.signature", PASS if info["signed"] else SKIP,
            "signature chain present (not cryptographically verified by SymPort)" if info["signed"]
            else "unsigned package")
    rep.data["sis"] = {k: info[k] for k in ("size", "signed", "data_units")} | {
        "files": [f["target"] for f in info["files"]]}
