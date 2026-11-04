"""Application kit: the application plus the runtime packages it declares, in install order.

SymPort only orders and packs what the user supplies. It never downloads a runtime on its own,
never treats a missing runtime as installed and never claims that installation succeeded.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import zipfile
from pathlib import PurePosixPath

from symport.catalog.packages import validate_package

from .analysis import analyze_package, match_provided, provided_summary

SCHEMA = "symport.bundle/1"
MAX_PACKAGES = 12
MAX_BYTES = 64 * 1024 * 1024


def _safe(name: str) -> str:
    stem = PurePosixPath(str(name).replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)[:80].strip("._")
    if not re.search(r"\.sisx?$", stem, re.I):
        raise ValueError("Kit packages must be SIS/SISX files")
    return stem


def _order(summaries: list[dict]) -> list[int]:
    """Topological order of runtime packages: a package installs after the packages it depends on."""
    n = len(summaries)
    deps = {i: set() for i in range(n)}
    for i, s in enumerate(summaries):
        for dep in s["dependencies"]:
            hit = match_provided(dep, [m for j, m in enumerate(summaries) if j != i])
            if hit:
                deps[i].add(next(j for j, m in enumerate(summaries) if m is hit["package"]))
    order, state = [], {}

    def visit(i):
        if state.get(i) == 1:
            raise ValueError("Runtime packages depend on each other in a cycle")
        if state.get(i) == 2:
            return
        state[i] = 1
        for j in sorted(deps[i]):
            visit(j)
        state[i] = 2
        order.append(i)

    for i in range(n):
        visit(i)
    return order


def build_bundle(app_name: str, app_raw: bytes, runtimes: list[tuple[str, bytes]], *, target=None,
                 firmware_dlls=None, firmware_source=None, allow_incomplete: bool = False) -> dict:
    if len(runtimes) > MAX_PACKAGES:
        raise ValueError(f"At most {MAX_PACKAGES} runtime packages per kit")
    if len(app_raw) + sum(len(r) for _, r in runtimes) > MAX_BYTES:
        raise ValueError("Kit exceeds 64 MiB")
    app_file = _safe(app_name)
    validate_package(app_file, app_raw)
    names = [app_file]
    summaries = []
    for name, raw in runtimes:
        safe = _safe(name)
        if safe in names:
            raise ValueError("Duplicate package name in kit: " + safe)
        validate_package(safe, raw)
        names.append(safe)
        summaries.append(provided_summary(raw))
    analysis = analyze_package(app_raw, name=app_file, target=target, firmware_dlls=firmware_dlls,
                               firmware_source=firmware_source, provided=summaries)
    order = _order(summaries)
    unresolved = [d for d in analysis["declared"] if not d["status"].startswith("provided-by-bundle")]
    for i in range(len(summaries)):
        sub = analyze_package(runtimes[i][1], name=names[i + 1], target=target,
                              provided=[s for j, s in enumerate(summaries) if j != i])
        unresolved += [{**d, "needed_by": names[i + 1]} for d in sub["declared"]
                       if not d["status"].startswith("provided-by-bundle")]
    def needed(i):
        mine = summaries[i]
        wanted = [d for d in analysis["declared"] if d["matched_package"] and d["matched_package"]["uid"] == f"{mine['uid']:#010x}"]
        return bool(wanted) or any(match_provided(dep, [mine]) for j, other in enumerate(summaries) if j != i for dep in other["dependencies"])

    unused = [names[i + 1] for i in range(len(summaries)) if not needed(i)]
    sequence = [(names[i + 1], runtimes[i][1], "runtime") for i in order] + [(app_file, app_raw, "application")]
    entries = []
    for position, (name, raw, role) in enumerate(sequence, 1):
        info = provided_summary(raw)
        entries.append({"position": position, "file": f"{position:02d}-{name}", "name": (info["names"] or [name])[0],
                        "role": role, "uid": f"{info['uid']:#010x}", "version": ".".join(map(str, info["version"] or [])),
                        "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    complete = not unresolved
    result = {"schema": SCHEMA, "status": "complete" if complete else "incomplete", "order": entries,
              "unresolved": unresolved, "unused_runtimes": unused, "analysis": analysis,
              "levels": {"static": "ordered", "installation": "not-tested", "runtime": "not-tested", "physical_device": "not-tested"},
              "instructions": [
                  "Copy the files to the phone in the numbered order and open each one in File manager.",
                  "The phone's own installer asks for confirmation and checks certificates; SymPort cannot do that for you.",
                  "Install the runtime packages first, the application last. Record any installer message verbatim.",
              ],
              "limitations": ["Ordering is derived from declared dependencies; it is not proof that the phone will accept the packages.",
                              "Packages you supply are not verified for rights, provenance or signature trust by SymPort."]}
    if complete or allow_incomplete:
        buffer = io.BytesIO()
        manifest = {k: result[k] for k in ("schema", "status", "order", "unresolved", "levels", "limitations")}
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry, (_, raw, _) in zip(entries, sequence, strict=True):
                archive.writestr(zipfile.ZipInfo(entry["file"], (2026, 1, 1, 0, 0, 0)), raw)
            archive.writestr(zipfile.ZipInfo("manifest.json", (2026, 1, 1, 0, 0, 0)),
                             json.dumps(manifest, indent=1, ensure_ascii=False))
            archive.writestr(zipfile.ZipInfo("INSTALL.txt", (2026, 1, 1, 0, 0, 0)),
                             "\n".join(result["instructions"] + [""] + [f"{e['position']}. {e['file']}  ({e['role']})" for e in entries]
                                       + ([""] + ["INCOMPLETE: unresolved dependencies listed in manifest.json"] if not complete else [])) + "\n")
        result["zip_name"] = re.sub(r"\.sisx?$", "", app_file, flags=re.I) + "-kit.zip"
        result["zip"] = base64.b64encode(buffer.getvalue()).decode()
    else:
        result["zip"] = None
        result["zip_name"] = None
    return result
