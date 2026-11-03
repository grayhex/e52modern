"""Static validation of built theme files (theme/dist/<variant>).

Reuses the existing low-level validator ``tools/s60/s60inspect.py`` for SKN/MBM/MIF structure and
adds cross-file, package, UID, bitmap-size and palette checks. Everything here is *static*:
passing proves internal consistency of the files, NOT that the E52 firmware accepts the theme.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from symport.backends import nokia_skin
from symport.config import Config
from symport.report import DEVICE, FAIL, FIRMWARE, PASS, SKIP, UNKNOWN, WARN, Report
from symport.theme import pkgfile, skin_src, uids
from symport.util import artifact_entry

VARIANTS = ("light", "dark")
S60_30_UID = 0x101F7961
S60_50_UID = 0x1028315F
SKINS_SUPPORT_UID = 0xA00000EB
SCALABLE_SKINS_UID = 0x10207113
MIN_CONTRAST = 4.5


def luminance(rgb: tuple[int, int, int]) -> float:
    def ch(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(fg: str, bg: str) -> float:
    def rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    la, lb = luminance(rgb(fg)), luminance(rgb(bg))
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def dist_dir(cfg: Config, variant: str) -> Path:
    return cfg.repo / "theme" / "dist" / variant


def find_base(cfg: Config, variant: str) -> Path | None:
    """Base path (no extension) of the built skin: the single .pkg in theme/dist/<variant>."""
    pkgs = sorted(dist_dir(cfg, variant).glob("*.pkg"))
    return pkgs[0].with_suffix("") if len(pkgs) == 1 else None


def check_palette(cfg: Config, variant: str, rep: Report) -> None:
    path = cfg.repo / "theme" / "colours.json"
    if not path.is_file():
        rep.add("palette.file", FAIL, "theme/colours.json missing")
        return
    data = json.loads(path.read_text(encoding="utf-8")).get(variant)
    if not data:
        rep.add("palette.variant", FAIL, f"variant {variant!r} missing in colours.json")
        return
    bad, mismatched = [], []
    for row in data["contrast"]:
        actual = contrast(row["fg"], row["bg"])
        if abs(actual - row["contrast"]) > 0.01:
            mismatched.append((row["role"], row["contrast"], actual))
        if actual < MIN_CONTRAST:
            bad.append((row["role"], actual))
    rep.add("palette.contrast", FAIL if bad else PASS,
            f"{len(data['contrast'])} text/background pairs, minimum WCAG ratio {MIN_CONTRAST}:1"
            + (f"; below threshold: {bad}" if bad else ""),
            pairs=len(data["contrast"]), minimum=min(contrast(r["fg"], r["bg"]) for r in data["contrast"]))
    rep.add("palette.recorded", FAIL if mismatched else PASS,
            "recorded contrast values match a fresh WCAG computation"
            + (f"; mismatched: {mismatched}" if mismatched else ""))


def check_manifest(cfg: Config, rep: Report) -> None:
    path = cfg.repo / "theme" / "manifest.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    status = m.get("status")
    if not isinstance(status, dict):
        rep.add("manifest.status", FAIL, "manifest.status must be a structured object "
                "(see docs/STATUS.md); the old free-text status is obsolete")
        return
    stale = "ASSETS ONLY" in json.dumps(status)
    dev = status.get("physical_device")
    rep.add("manifest.status", FAIL if stale else PASS,
            "manifest status is current" if not stale else "manifest still claims 'assets only'")
    rep.add("manifest.no_device_claim", PASS if dev == "not-tested" else WARN,
            f"manifest physical_device = {dev!r}",
            note="must stay 'not-tested' until a signed manual checklist is recorded")
    geo = m.get("geometry", {})
    rep.add("manifest.geometry", PASS if geo.get("screen") == [240, 320] else FAIL,
            f"screen {geo.get('screen')} (E52 is 240x320 portrait)")


def inspect_variant(cfg: Config, variant: str) -> Report:
    rep = Report(f"theme inspect --variant {variant}")
    rep.verification["static_automated"] = True
    d = dist_dir(cfg, variant)
    base = find_base(cfg, variant)
    if base is None:
        rep.add("dist.present", FAIL, f"no single built skin in {d} — run `symport theme build`")
        return rep
    rep.add("dist.present", PASS, f"found {base.name}", path=str(d))
    for ext in (".skn", ".mbm", ".mif", ".pkg"):
        p = base.with_suffix(ext)
        if p.is_file():
            rep.artifacts.append(artifact_entry(p, cfg.repo))
        else:
            rep.add(f"dist.{ext[1:]}", FAIL, f"missing {p.name}")

    # --- low-level structure via the existing validator
    s60 = nokia_skin.load_s60inspect(cfg)
    notes: list[str] = []
    bitmaps: list[tuple] = []
    try:
        problems, bitmaps = s60.inspect_mbm(str(base.with_suffix(".mbm")), notes.append)
        rep.add("mbm.structure", FAIL if problems else PASS,
                f"{len(bitmaps)} bitmaps" if not problems else "; ".join(problems),
                bitmaps=len(bitmaps))
        mp, icons = s60.inspect_mif(str(base.with_suffix(".mif")), len(bitmaps), notes.append)
        rep.add("mif.structure", FAIL if mp else PASS,
                f"{icons} icons, every MIF index resolves to an MBM bitmap" if not mp else "; ".join(mp),
                icons=icons)
        sp = s60.inspect_skn(str(base.with_suffix(".skn")), str(base), notes.append)
        rep.add("skn.structure", FAIL if sp else PASS,
                "declared length matches file size; .mbm/.mif names present" if not sp else "; ".join(sp))
    except (OSError, struct.error) as e:
        rep.add("structure.read", FAIL, f"cannot read skin files: {e}")
        return rep

    skn = base.with_suffix(".skn").read_bytes()
    skn_pid1 = struct.unpack_from("<I", skn, 8)[0]

    # --- package file
    try:
        pkg = pkgfile.parse(base.with_suffix(".pkg").read_text(encoding="ascii", errors="replace"))
    except (pkgfile.PkgError, OSError) as e:
        rep.add("pkg.parse", FAIL, str(e))
        return rep
    rep.add("pkg.parse", PASS, f"'{pkg.name}' uid {pkg.uid:#010x}, {len(pkg.files)} file entries")
    uidhex = f"{pkg.uid:08x}"
    rep.add("uid.consistency",
            PASS if skn_pid1 == pkg.uid else FAIL,
            f"pkg UID {pkg.uid:#010x} vs SKN PID1 {skn_pid1:#010x}")
    src = cfg.repo / "theme" / "src" / variant
    if (src / "skin.txt").is_file():
        suid = skin_src.skin_uid(src / "skin.txt")
        rep.add("uid.source", PASS if suid == pkg.uid else FAIL,
                f"skin.txt UID {suid and hex(suid)} vs pkg UID {pkg.uid:#010x}")
    cls = uids.classify(pkg.uid)
    note = uids.collision_note(pkg.uid)
    rep.add("uid.range", WARN if cls == "test" else (FAIL if pkg.uid in uids.KNOWN_SKIN_UIDS else PASS),
            f"UID class: {cls}. {note}", uid_class=cls)
    other = [v for v in VARIANTS if v != variant]
    for ov in other:
        ob = find_base(cfg, ov)
        if ob is not None:
            opkg = pkgfile.parse(ob.with_suffix(".pkg").read_text(encoding="ascii", errors="replace"))
            rep.add(f"uid.distinct.{ov}", PASS if opkg.uid != pkg.uid else FAIL,
                    f"UID differs from variant {ov}" if opkg.uid != pkg.uid else "same UID as another variant")

    # --- declared dependencies
    has30 = S60_30_UID in pkg.platform_deps
    rep.add("pkg.platform", PASS if has30 else FAIL,
            "declares S60 3.x platform UID 0x101F7961 (Series60v3.0) - required for E52 (S60 3rd FP2)"
            if has30 else "S60 3.x platform dependency 0x101F7961 missing")
    rep.add("pkg.platform_v5", PASS if S60_50_UID in pkg.platform_deps else WARN,
            "also declares S60 5.x (0x1028315F); harmless for E52, informational")
    missing_deps = [hex(x) for x in (SKINS_SUPPORT_UID, SCALABLE_SKINS_UID) if x not in pkg.package_deps]
    rep.add("pkg.skin_support", FAIL if missing_deps else PASS,
            "requires skin support packages 0xA00000EB and 0x10207113"
            if not missing_deps else f"missing dependencies: {missing_deps}")

    # --- install paths
    exp = {
        f"!:\\resource\\skins\\{uidhex}\\{base.name}.mbm": base.name + ".mbm",
        f"!:\\resource\\skins\\{uidhex}\\{base.name}.mif": base.name + ".mif",
        f"!:\\private\\10207114\\import\\{uidhex}\\{base.name}.skn": base.name + ".skn",
    }
    got = {e.dest.lower(): e for e in pkg.files}
    problems = []
    for dest, src_name in exp.items():
        e = got.get(dest.lower())
        if e is None:
            problems.append(f"missing install line for {dest}")
        elif e.source != src_name:
            problems.append(f"{dest}: source {e.source!r}, expected {src_name!r}")
        elif not (d / e.source).is_file():
            problems.append(f"source file {e.source} not found in dist")
    unexpected = [e.dest for e in pkg.files
                  if e.dest.lower() not in {k.lower() for k in exp} and e.options != "FN"]
    if unexpected:
        problems.append(f"unexpected install targets: {unexpected}")
    rep.add("pkg.paths", FAIL if problems else PASS,
            "install targets match S60 3rd skin layout (resource\\skins + private\\10207114\\import)"
            if not problems else "; ".join(problems))
    rep.add("pkg.vendor", PASS if pkg.vendor else FAIL, f"vendor {pkg.vendor!r}")

    # --- bitmap sizes / masks against the generated sources
    if (src / "skin.txt").is_file() and (src / "gfx").is_dir():
        try:
            expected = skin_src.expected_bitmaps(src)
            layout = []
            for e in expected:
                layout.append((e.size[0], e.size[1], 16))
                if e.mask:
                    layout.append((e.mask_size[0], e.mask_size[1], 8))
            actual = [(w, h, bpp) for (w, h, bpp, _c) in bitmaps]
            rep.add("mbm.match_sources", PASS if layout == actual else FAIL,
                    f"{len(expected)} bitmaps (+masks) in .mbm match skin.txt/gfx order, sizes and depths"
                    if layout == actual else
                    f"MBM layout differs from sources ({len(actual)} actual vs {len(layout)} expected)",
                    expected=len(layout), actual=len(actual))
            masks = sum(1 for e in expected if e.mask)
            rep.add("mif.match_sources", PASS if icons == len(expected) else FAIL,
                    f"MIF icon count {icons} == {len(expected)} bitmap entries ({masks} with soft mask)")
        except (OSError, ValueError) as e:
            rep.add("mbm.match_sources", FAIL, f"cannot compare with sources: {e}")
    else:
        rep.add("mbm.match_sources", SKIP, "theme/src not present; source comparison skipped")

    check_palette(cfg, variant, rep)
    check_manifest(cfg, rep)

    # --- what static checks cannot establish
    rep.add("firmware.acceptance", UNKNOWN,
            "whether the E52 firmware accepts this .skn/.mif/.mbm is not established by static checks",
            level=FIRMWARE)
    rep.add("device.install", UNKNOWN, "no physical Nokia E52 test has been recorded", level=DEVICE)
    rep.limitations += [
        "Static validation only: SKN internals are checked for envelope/length, not decoded item-by-item.",
        "The MIF/MBM pair is produced by tools/s60/mifbuild.py, "
        "not by Nokia's mifconv; its acceptance by firmware is unverified.",
        "A theme cannot change system geometry (clock, Active Standby, menu grid, key assignments).",
    ]
    rep.data["variant"] = variant
    rep.data["package"] = {"name": pkg.name, "uid": f"{pkg.uid:#010x}", "files": len(pkg.files)}
    return rep
