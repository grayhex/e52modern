"""SymPort command line interface (``python -m symport`` / ``symport``)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from symport import __version__, doctor, emulator
from symport.analysis import compat
from symport.application import analyze as app_analyze
from symport.application import workflow
from symport.backends import modern_sdk, nokia_skin
from symport.config import Config, ConfigError, find_repo_root
from symport.devices import profiles as prof
from symport.devices import stage
from symport.report import EXIT_USAGE, FAIL, PASS, Report
from symport.reports import matrix
from symport.theme import inspect as tinspect
from symport.theme import package as tpackage
from symport.theme import reproduce

DEFAULT_TARGET = "nokia-e52"
VARIANTS = ("light", "dark")


def _common() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--repo", type=Path, help="E52Modern checkout (default: auto-detect)")
    p.add_argument("--json", action="store_true", help="print the machine-readable JSON report")
    p.add_argument("--report", type=Path, metavar="FILE", help="also write the JSON report to FILE")
    return p


def build_parser() -> argparse.ArgumentParser:
    common = _common()
    top = argparse.ArgumentParser(
        prog="symport", description="SymPort - Symbian S60 themes and applications toolkit "
        "(part of E52Modern). Reports always separate static checks from emulator and device evidence.")
    top.add_argument("--version", action="version", version=f"symport {__version__}")
    sub = top.add_subparsers(dest="group", required=True, metavar="<command>")

    sub.add_parser("doctor", parents=[common], help="survey the environment and backends")

    p_prof = sub.add_parser("profile", help="device profiles").add_subparsers(dest="action", required=True)
    p_prof.add_parser("list", parents=[common], help="list profiles")
    ps = p_prof.add_parser("show", parents=[common], help="show a profile with fact provenance")
    ps.add_argument("id", nargs="?", default=DEFAULT_TARGET)

    theme = sub.add_parser("theme", help="E52 CLEAR theme pipeline").add_subparsers(dest="action", required=True)
    tb = theme.add_parser("build", parents=[common], help="build theme variants (tools/build_theme.py)")
    tb.add_argument("--variant", choices=(*VARIANTS, "all"), default="all")
    tb.add_argument("--bootstrap", action="store_true", help="build skc/bmconv first if missing (tools/s60/build.sh)")
    ti = theme.add_parser("inspect", parents=[common], help="static validation of built theme files")
    ti.add_argument("--variant", choices=(*VARIANTS, "all"), default="all")
    ti.add_argument("--reproducible", action="store_true",
                    help="also rebuild twice in isolation and compare (slow)")
    tp = theme.add_parser("package", parents=[common], help="create a SIS from a built theme")
    tp.add_argument("--variant", choices=(*VARIANTS, "all"), default="all")
    tp.add_argument("--backend", choices=("auto", "makesis", "native", "modern-sdk"),
                    help="auto = official makesis if present, else 'unsupported' (never a silent fallback)")
    tp.add_argument("--output", type=Path, help="output directory (default build/symport/theme/<variant>)")
    tp.add_argument("--cert", type=Path, help="PEM certificate chain for official signsis")
    tp.add_argument("--key", type=Path, help="private key for official signsis")

    sis = sub.add_parser("sis", help="SIS tools").add_subparsers(dest="action", required=True)
    si = sis.add_parser("inspect", parents=[common], help="inspect a SIS/SISX package")
    si.add_argument("file", type=Path)
    si.add_argument("--target", default=DEFAULT_TARGET)
    si.add_argument("--firmware-profile", type=Path)

    sc = sis.add_parser("compare", parents=[common],
                        help="compare installer-relevant content of two SIS files (e.g. MakeSIS vs native writer)")
    sc.add_argument("a", type=Path)
    sc.add_argument("b", type=Path)

    app = sub.add_parser("app", help="native applications (via symbian-platform)").add_subparsers(
        dest="action", required=True)
    ai = app.add_parser("init", parents=[common], help="create a project with the SDK's starter")
    ai.add_argument("--name", required=True)
    ai.add_argument("--target", default=DEFAULT_TARGET)
    ai.add_argument("--dest", type=Path, help="project directory (default ./<name>)")
    ab = app.add_parser("build", parents=[common], help="build an E32 image")
    ab.add_argument("--project", type=Path, required=True)
    ab.add_argument("--target", default=DEFAULT_TARGET)
    ab.add_argument("--mode", choices=("app", "toolchain"), default="app",
                    help="app: `symbian app build` (installed native SDK); toolchain: low-level `symbian build`")
    ab.add_argument("--compiler", help="ARM-capable clang++ (toolchain mode); ninja is looked up next to it")
    ab.add_argument("--linker", help="ld.lld (toolchain mode)")
    an = app.add_parser("inspect", parents=[common], help="inspect a project or an E32/SIS/ELF file")
    an.add_argument("file", nargs="?", type=Path)
    an.add_argument("--project", type=Path)
    an.add_argument("--target", default=DEFAULT_TARGET)
    an.add_argument("--firmware-profile", type=Path)
    an.add_argument("--cross-check", action="store_true",
                    help="compare E32 fields with `symbian inspect --format e32` (independent implementation)")
    aa = app.add_parser("analyze", parents=[common], help="compatibility analysis of a project/binary")
    aa.add_argument("path", type=Path)
    aa.add_argument("--target", default=DEFAULT_TARGET)
    aa.add_argument("--firmware-profile", type=Path,
                    help="user-supplied firmware profile (DLL/ordinal table); without it imports stay 'unknown'")
    aa.add_argument("--cross-check", action="store_true",
                    help="compare E32 fields with `symbian inspect --format e32` (independent implementation)")
    ap = app.add_parser("package", parents=[common], help="package a built project as SIS")
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--target", default=DEFAULT_TARGET)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--cert", type=Path)
    ap.add_argument("--key", type=Path)

    emu = sub.add_parser("emulator", help="EKA2L1 integration").add_subparsers(dest="action", required=True)
    emu.add_parser("list", parents=[common], help="detect emulator backends")
    et = emu.add_parser("test", parents=[common], help="run a SIS in an isolated emulator session")
    et.add_argument("sis", type=Path)
    et.add_argument("--target", default=DEFAULT_TARGET)

    dev = sub.add_parser("device", help="physical device (via symbian-platform)").add_subparsers(
        dest="action", required=True)
    dev.add_parser("list", parents=[common], help="list USB candidates")
    di = dev.add_parser("info", parents=[common], help="describe a connected device")
    di.add_argument("--device", help="selector from `device list`")
    ds = dev.add_parser("stage", parents=[common], help="copy a SIS to the phone (does NOT install it)")
    ds.add_argument("sis", type=Path)
    ds.add_argument("--device", help="selector from `device list`")

    rp = sub.add_parser("report", help="report utilities").add_subparsers(dest="action", required=True)
    rm = rp.add_parser("matrix", parents=[common], help="compatibility matrix from saved JSON reports")
    rm.add_argument("directory", type=Path)
    return top


def _merge(command: str, parts: dict[str, Report]) -> Report:
    if len(parts) == 1:
        only = next(iter(parts.values()))
        only.command = command
        return only
    rep = Report(command)
    rep.verification = {"static_automated": any(r.verification.get("static_automated") for r in parts.values()),
                        "emulator": "not-tested", "physical_device": "not-tested"}
    for name, r in parts.items():
        r.finalize()
        for c in r.checks:
            rep.add(f"{name}.{c.id}", c.status, c.message, c.level, **c.evidence)
        rep.artifacts += r.artifacts
        rep.limitations += [x for x in r.limitations if x not in rep.limitations]
        rep.data[name] = r.data
        if r.status == "unsupported":
            rep.status = "unsupported"
    return rep


def _variants(v: str) -> list[str]:
    return list(VARIANTS) if v == "all" else [v]


def _cfg(args) -> Config:
    return Config.load(find_repo_root(explicit=args.repo))


def _profile(cfg: Config, target: str) -> prof.Profile:
    return prof.get_profile(target, cfg.profiles_dirs)


def _theme_build(cfg: Config, args) -> Report:
    rep = Report("theme build")
    t = nokia_skin.tools(cfg)
    if (not t.skc.exists() or not t.bmconv.exists()) and args.bootstrap:
        r = nokia_skin.bootstrap(cfg)
        rep.add("bootstrap", PASS if r.ok else FAIL, "tools/s60/build.sh " + ("succeeded" if r.ok else r.output[-400:]),
                "environment")
        if not r.ok:
            return rep
        t = nokia_skin.tools(cfg)
    if t.missing():
        rep.add("tools", FAIL, f"missing: {', '.join(t.missing())}", "environment")
        rep.unsupported("Skin tools are not built.", ["Run tools/s60/build.sh (needs g++), or pass --bootstrap"])
        return rep
    variants = _variants(args.variant)
    r = nokia_skin.build_variant(cfg, variants)
    rep.add("pipeline", PASS if r.ok else FAIL,
            "tools/build_theme.py " + " ".join(variants) + (" succeeded" if r.ok else f" failed: {r.output[-600:]}"),
            "static")
    if not r.ok:
        return rep
    parts = {v: tinspect.inspect_variant(cfg, v) for v in variants}
    merged = _merge("inspect", parts)
    for c in merged.checks:
        rep.checks.append(c)
    rep.artifacts += merged.artifacts
    rep.limitations += merged.limitations
    rep.verification["static_automated"] = True
    rep.data["variants"] = variants
    rep.data["pipeline_output_tail"] = r.output[-1200:]
    return rep


def _dispatch(args) -> Report | None:
    g, a = args.group, getattr(args, "action", None)
    if g == "doctor":
        return doctor.survey(args.repo)
    cfg = _cfg(args)
    if g == "profile":
        profs = prof.list_profiles(cfg.profiles_dirs)
        rep = Report(f"profile {a}")
        if a == "list":
            rep.data["profiles"] = [p.summary() for p in profs]
            rep.add("profiles", PASS, f"{len(profs)} profile(s): " + ", ".join(p.id for p in profs))
        else:
            p = prof.get_profile(args.id, cfg.profiles_dirs)
            rep.data["profile"] = {"id": p.id, "path": str(p.path),
                                   "facts": {k: v for k, v in p.facts()}}
            unknown = [k for k, v in p.facts() if v["status"] == "unknown"]
            rep.add("profile", PASS, f"{p.id}: {len(p.facts())} facts, {len(unknown)} unknown")
            rep.limitations.append("Facts marked 'unknown' were not verified; nothing here was "
                                   "measured on a physical device.")
        return rep
    if g == "theme":
        if a == "build":
            return _theme_build(cfg, args)
        if a == "inspect":
            parts = {v: tinspect.inspect_variant(cfg, v) for v in _variants(args.variant)}
            if args.reproducible:
                for v in list(parts):
                    parts[f"{v}.repro"] = reproduce.check_reproducible(cfg, v)
            return _merge("theme inspect", parts)
        if a == "package":
            parts = {v: tpackage.package_variant(cfg, v, args.backend, args.output, args.cert, args.key)
                     for v in _variants(args.variant)}
            return _merge("theme package", parts)
    if g == "sis" and a == "compare":
        from symport.sis import compare as sis_compare
        from symport.sis.fields import SisFormatError
        rep = Report("sis compare")
        try:
            diffs = sis_compare.compare(args.a.read_bytes(), args.b.read_bytes())
        except (OSError, SisFormatError) as e:
            rep.add("sis.parse", FAIL, str(e))
            return rep
        rep.verification["static_automated"] = True
        rep.data["differences"] = diffs
        rep.add("sis.equivalent", PASS if not diffs else FAIL,
                "installer-relevant content is identical" if not diffs
                else f"{len(diffs)} difference(s): " + "; ".join(d["field"] for d in diffs))
        rep.limitations.append("Compares identity, files and dependency counts only; byte layout and compression "
                               "may differ legitimately. Says nothing about acceptance by a phone.")
        return rep
    if g == "sis" and a == "inspect":
        fw = compat.load_firmware_profile(args.firmware_profile) if args.firmware_profile else None
        return app_analyze.analyze_sis(args.file, _profile(cfg, args.target), fw)
    if g == "app":
        sdk = modern_sdk.locate()
        if a == "init":
            return workflow.init_project(args.name, args.dest or Path(args.name),
                                         _profile(cfg, args.target), sdk)
        if a == "build":
            return workflow.build_project(args.project, _profile(cfg, args.target), sdk, args.mode,
                                          args.compiler, args.linker)
        if a == "package":
            return workflow.package_project(args.project, _profile(cfg, args.target), sdk,
                                            args.output, args.cert, args.key)
        profile = _profile(cfg, args.target)
        fw = compat.load_firmware_profile(args.firmware_profile) if getattr(args, "firmware_profile", None) else None
        if a == "inspect":
            if args.project:
                return workflow.inspect_project(args.project, profile)
            if not args.file:
                raise ConfigError("give a file or --project")
            return app_analyze.analyze_file(args.file, profile, fw, args.cross_check)
        if a == "analyze":
            if args.path.is_dir():
                return app_analyze.analyze_project(args.path, profile, fw, args.cross_check)
            return app_analyze.analyze_file(args.path, profile, fw, args.cross_check)
    if g == "emulator":
        if a == "list":
            return emulator.list_emulators(cfg)
        return emulator.test_package(cfg, args.sis, _profile(cfg, args.target))
    if g == "device":
        if a == "list":
            return stage.device_list()
        if a == "info":
            return stage.device_info(args.device)
        return stage.device_stage(args.sis, args.device)
    if g == "report" and a == "matrix":
        rows = matrix.build(matrix.load_reports(args.directory))
        rep = Report("report matrix")
        rep.data["rows"] = rows
        rep.data["markdown"] = matrix.to_markdown(rows)
        rep.add("matrix", PASS, f"{len(rows)} report(s) aggregated")
        return rep
    return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rep = _dispatch(args)
    except (ConfigError, prof.ProfileError, compat.FirmwareProfileError) as e:
        if getattr(args, "json", False):
            print(json.dumps({"schema": "symport.report/1", "status": "error", "error": str(e)}))
        else:
            print(f"symport: error: {e}", file=sys.stderr)
        return EXIT_USAGE
    if rep is None:
        parser.error("unknown command")
    rep.finalize()
    if getattr(args, "report", None):
        rep.write(args.report)
    if getattr(args, "json", False):
        print(rep.to_json())
    else:
        print(rep.to_text())
        if args.group == "report" and rep.data.get("markdown"):
            print(rep.data["markdown"])
    return rep.exit_code


if __name__ == "__main__":
    sys.exit(main())
