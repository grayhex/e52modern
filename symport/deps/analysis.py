"""Static dependency analysis of a SIS/SISX package.

Answers "what does this package need?" from its own structure: declared platform IDs, declared package
dependencies, imported DLLs of its uncompressed E32 images, requested capabilities and payload hints.
It never says that anything is installed or that the application runs: unknown stays unknown.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from symport.analysis import e32
from symport.sis import reader

from . import runtimes as rt

SCHEMA = "symport.dependencies/1"
LEVELS = {"static": "analysed", "installation": "not-tested", "runtime": "not-tested", "physical_device": "not-tested"}


def _hex(uid):
    return None if uid is None else f"{uid:#010x}"


def _version(v):
    return None if v is None else ".".join(str(x) for x in v)


def _norm_target(target) -> dict:
    target = target if isinstance(target, dict) else {}
    return {k: str(target.get(k) or "")[:120] for k in ("model", "rm", "firmware", "os")}


def device_profile(target: dict) -> str | None:
    from symport.phone.registry import target_profile
    resolved = target_profile(target)
    return resolved["id"] if resolved else None


def _basename(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).name.lower()


def _dll_key(dll: str) -> str:
    """``QtCore{00040703}[2001e61c].dll`` -> ``qtcore.dll``."""
    stem = re.sub(r"\{[0-9a-fA-F]{8}\}|\[[0-9a-fA-F]{8}\]", "", dll)
    stem = stem.rsplit(".", 1)[0].strip().lower()
    return stem + ".dll"


def provided_summary(raw: bytes) -> dict:
    """What a candidate runtime package declares about itself (UID, name, version, own dependencies)."""
    info = reader.inspect(raw)
    return {"uid": info["package"]["uid"], "names": info["package"]["names"], "version": info["package"]["version"],
            "dependencies": [i for i in info["dependencies"]["items"] if i["kind"] == "dependency"],
            "dlls": sorted({_basename(f["target"]) for f in info["files"] if f["target"].lower().endswith(".dll")})}


def _version_ok(have, need_from, need_to):
    if have is None or need_from is None:
        return None
    if tuple(have) < tuple(need_from):
        return False
    return not (need_to is not None and tuple(have) > tuple(need_to))


def match_provided(dependency: dict, provided: list[dict]) -> dict | None:
    """Which supplied package satisfies a declared dependency, and how strongly."""
    for candidate in provided:
        if dependency["uid"] is not None and candidate["uid"] == dependency["uid"]:
            ok = _version_ok(candidate["version"], dependency["from_version"], dependency["to_version"])
            return {"package": candidate, "basis": "uid", "version_ok": ok}
    family = rt.runtime_for_name(" ".join(dependency["names"]))
    for candidate in provided:
        if family and any(rt.runtime_for_name(n) == family for n in candidate["names"]):
            ok = _version_ok(candidate["version"], dependency["from_version"], dependency["to_version"])
            return {"package": candidate, "basis": "name", "version_ok": ok}
    return None


def analyze_package(raw: bytes, *, name: str = "package.sis", target=None, firmware_dlls=None,
                    firmware_source: str | None = None, provided: list[dict] | None = None) -> dict:
    info = reader.inspect(raw)
    target = _norm_target(target)
    profile = device_profile(target)
    provided = provided or []
    issues: list[str] = []

    # --- platform / target-device IDs ---------------------------------------------------------
    platforms = []
    from symport.phone.platforms import platform_state
    from symport.phone.registry import registry
    spec = registry().get(profile, {})
    accepted, uncertain, os_mismatch = platform_state(spec, target['os'])
    for item in info["dependencies"]["items"]:
        if item["kind"] != "target-device":
            continue
        known = rt.platform(item["uid"])
        if item["uid"] in accepted:
            relation, basis = "accepted-by-target", accepted[item["uid"]]
        elif item["uid"] in uncertain:
            relation, basis = "release-unverified", "OS release is unknown; model does not prove Belle"
        elif known:
            relation, basis = ("not-accepted-by-target" if profile else "target-unknown"), "known-platform"
        else:
            relation, basis = "unknown-platform-id", "unrecognised"
        # UID establishes a platform family, not the installed product-package version.
        # Nonzero version ranges need a matching firmware product inventory, which we do not infer.
        version_required = any(item.get("from_version") or []) or item.get("to_version") is not None
        if relation == "accepted-by-target" and version_required:
            relation = "product-version-unknown"
        platforms.append({"min_version": _version(item.get("from_version")), "max_version": _version(item.get("to_version")),"uid": _hex(item["uid"]), "label": (known or {}).get("name") or (item["names"] or ["?"])[0],
                          "symbian": (known or {}).get("symbian"), "relation": relation, "basis": basis,
                          "source": (known or {}).get("source")})
    if not platforms:
        platform_verdict = "unknown"
        issues.append("platform-undeclared")
    elif not profile:
        platform_verdict = "unknown"
        issues.append("platform-target-unknown")
    elif any(p["relation"] == "accepted-by-target" for p in platforms):
        platform_verdict = "supported-static"
    elif any(p["relation"] in ("unknown-platform-id", "product-version-unknown", "release-unverified") for p in platforms):
        platform_verdict = "unknown"
        issues.append("platform-target-unknown")
    else:
        platform_verdict = "unsupported"
        issues.append("platform-unsupported")

    if os_mismatch:
        issues.append('target-os-mismatch')
        platform_verdict = 'unsupported'

    # --- declared package dependencies --------------------------------------------------------
    declared = []
    for item in info["dependencies"]["items"]:
        if item["kind"] != "dependency":
            continue
        label = " / ".join(item["names"]) or _hex(item["uid"])
        family = rt.runtime_for_name(" ".join(item["names"])) or rt.runtime_for_uid(item["uid"])
        hit = match_provided(item, provided)
        if hit:
            status = {True: "provided-by-bundle", False: "provided-version-too-old", None: "provided-version-unknown"}[hit["version_ok"]]
            if hit["basis"] == "name":
                status += "-by-name"
        else:
            status = "required-unverified"
        declared.append({"uid": _hex(item["uid"]), "name": label, "runtime": family,
                         "min_version": _version(item["from_version"]), "max_version": _version(item["to_version"]),
                         "status": status, "matched_package": hit and {"uid": _hex(hit["package"]["uid"]),
                                                                       "name": (hit["package"]["names"] or ["?"])[0],
                                                                       "basis": hit["basis"]}})
        if not status.startswith("provided-by-bundle") and status != "provided-version-unknown":
            issues.append("dependency-unverified" if status == "required-unverified" else "dependency-version")

    # --- payload and binaries -----------------------------------------------------------------
    payload_dlls = {_basename(f["target"]) for f in info["files"] if f["target"].lower().endswith(".dll")}
    payload_dlls |= {d for p in provided for d in p["dlls"]}
    hints = []
    if any(f["target"].lower().endswith((".py", ".pyc", ".pyo")) or "\\python\\" in f["target"].lower() for f in info["files"]):
        hints.append({"runtime": "pys60", "basis": "payload contains Python scripts (heuristic)"})
    binaries, imports_missing = [], []
    import_usage: dict[str, set[str]] = {}
    try:
        extracted = reader.extract(raw)
    except ValueError as exc:
        extracted = {}
        issues.append("payload-unreadable")
        binaries.append({"target": None, "note": str(exc)})
    capabilities: set[str] = set()
    restricted: set[str] = set()
    for path, blob in extracted.items():
        if not e32.is_e32(blob):
            continue
        a = e32.analyze(blob)
        entry = {"target": path, "kind": "dll" if a["is_dll"] else "exe", "secure_id": a["secure_id"],
                 "compression": a["compression"], "kernel": a["kernel"], "cpu": a["cpu"],
                 "capabilities": a["capabilities"], "imports": None, "imports_note": a["imports_note"]}
        capabilities.update(a["capabilities"] or [])
        restricted.update(a["restricted_capabilities"] or [])
        if a["imports"] is None:
            imports_missing.append(path)
        else:
            entry["imports"] = [i["name"] for i in a["imports"]]
            for imp in a["imports"]:
                import_usage.setdefault(_dll_key(imp["dll"]), set()).add(path)
        binaries.append(entry)
    if imports_missing:
        issues.append("imports-undecoded")
    if restricted:
        issues.append("restricted-capabilities")

    # --- imported DLLs, classified --------------------------------------------------------------
    firmware = {d.lower() for d in firmware_dlls} if firmware_dlls is not None else None
    system_imports, runtime_imports = [], {}
    for dll, users in sorted(import_usage.items()):
        family = rt.runtime_for_import(dll)
        if dll in payload_dlls:
            status = "package-provided"
        elif family:
            runtime_imports.setdefault(family, []).append(dll)
            status = "runtime-required-unverified"
        elif firmware is None:
            status = "unknown-no-firmware-data"
        elif dll in firmware:
            status = "firmware-profile-present"
        else:
            status = "firmware-profile-missing"
            issues.append("system-dll-missing")
        if status == "unknown-no-firmware-data":
            issues.append("system-dll-unverified")
        system_imports.append({"dll": dll, "runtime": family, "status": status, "used_by": sorted(users)})

    # --- runtimes ------------------------------------------------------------------------------
    runtimes_out = []
    families = {d["runtime"] for d in declared if d["runtime"]} | set(runtime_imports) | {h["runtime"] for h in hints}
    for family in sorted(families):
        spec = rt.RUNTIMES[family]
        via = []
        decl = [d for d in declared if d["runtime"] == family]
        if decl:
            via.append("declared-dependency")
        if family in runtime_imports:
            via.append("imported-dlls")
        if any(h["runtime"] == family for h in hints):
            via.append("payload-hint")
        if decl and all(d["status"].startswith("provided-by-bundle") for d in decl):
            status = "provided-by-bundle"
        else:
            status = "required-unverified"
            if "runtime-required-unverified" not in issues:
                issues.append("runtime-required-unverified")
        runtimes_out.append({"id": family, "title": spec["title"], "via": via, "status": status,
                             "min_version": next((d["min_version"] for d in decl if d["min_version"]), None),
                             "dlls": runtime_imports.get(family, []), "distribution": spec["distribution"]})

    for binary in binaries:
        if profile and binary.get('cpu') in ('x86', 'mcore'):
            issues.append('binary-abi-unsupported')
        if profile and binary.get('cpu') == 'armv6':
            issues.append('binary-abi-unknown' if spec.get('platform_family') == 'symbian3' else 'binary-abi-unsupported')
        if profile and binary.get('kernel') == 'eka1':
            issues.append('binary-kernel-unsupported')
        if profile and (str(binary.get('cpu', '')).startswith('unknown') or str(binary.get('kernel', '')).startswith('unknown')):
            issues.append('binary-abi-unknown')
    issues = list(dict.fromkeys(issues))
    blocking = {"platform-unsupported", "target-os-mismatch", "binary-abi-unsupported", "binary-kernel-unsupported", "system-dll-missing", "dependency-version"}
    unresolved = {"binary-abi-unknown", "platform-undeclared", "platform-target-unknown", "dependency-unverified", "runtime-required-unverified",
                  "imports-undecoded", "system-dll-unverified", "payload-unreadable"}
    if blocking & set(issues):
        verdict = "blocked"
    elif unresolved & set(issues):
        verdict = "unresolved"
    else:
        verdict = "satisfied-static"
    pkg_name = (info["package"]["names"] or [name])[0]
    result = {
        "schema": SCHEMA, "package": {"name": pkg_name, "uid": _hex(info["package"]["uid"]), "file": name,
                                      "version": _version(info["package"]["version"])},
        "target": target, "target_profile": profile, "platform_verdict": platform_verdict, "platforms": platforms,
        "declared": declared, "runtimes": runtimes_out, "system_imports": system_imports, "binaries": binaries,
        "capabilities": sorted(capabilities), "restricted_capabilities": sorted(restricted),
        "payload_dlls": sorted(payload_dlls), "hints": hints, "issues": issues, "verdict": verdict,
        "firmware": {"source": firmware_source, "dll_count": len(firmware)} if firmware is not None else None,
        "levels": dict(LEVELS),
        "limitations": [
            "Static analysis only: no installation or run was attempted and nothing is known to be installed.",
            "Compressed E32 images (bytepair/deflate) are not decoded, so their imported DLLs are unknown.",
            "A dependency present on a memory card does not prove it is installed on the phone.",
            "Unknown dependencies are never treated as installed or compatible.",
        ],
    }
    result["graph"] = build_graph(result)
    return result


def build_graph(result: dict) -> dict:
    """Nodes/edges for the dependency graph; ids are stable strings."""
    nodes, edges = [], []

    def node(node_id, label, kind, status=None):
        nodes.append({"id": node_id, "label": label, "kind": kind, "status": status})

    root = "pkg:" + result["package"]["file"]
    node(root, result["package"]["name"], "package", result["verdict"])
    for p in result["platforms"]:
        node("plat:" + p["uid"], p["label"], "platform", p["relation"])
        edges.append({"from": root, "to": "plat:" + p["uid"], "kind": "targets"})
    for d in result["declared"]:
        node("dep:" + (d["uid"] or d["name"]), d["name"] + (f" ≥ {d['min_version']}" if d["min_version"] else ""),
             "dependency", d["status"])
        edges.append({"from": root, "to": "dep:" + (d["uid"] or d["name"]), "kind": "requires"})
    for r in result["runtimes"]:
        node("rt:" + r["id"], r["title"], "runtime", r["status"])
        edges.append({"from": root, "to": "rt:" + r["id"], "kind": "needs-runtime"})
        for d in result["declared"]:
            if d["runtime"] == r["id"]:
                edges.append({"from": "dep:" + (d["uid"] or d["name"]), "to": "rt:" + r["id"], "kind": "is"})
    for s in result["system_imports"]:
        node("dll:" + s["dll"], s["dll"], "system-dll" if not s["runtime"] else "runtime-dll", s["status"])
        for user in s["used_by"]:
            edges.append({"from": "bin:" + user, "to": "dll:" + s["dll"], "kind": "imports"})
        if s["runtime"]:
            edges.append({"from": "dll:" + s["dll"], "to": "rt:" + s["runtime"], "kind": "belongs-to"})
    for b in result["binaries"]:
        if b.get("target"):
            node("bin:" + b["target"], b["target"].replace("\\", "/").rsplit("/", 1)[-1], "binary", None)
            edges.append({"from": root, "to": "bin:" + b["target"], "kind": "contains"})
    return {"nodes": nodes, "edges": edges}
