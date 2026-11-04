"""Dependency & Runtime Manager: static dependency analysis and ordered application kits."""
from __future__ import annotations

import base64
import io
import json
import zipfile

import pytest

from symport.deps import analyze_package, build_bundle
from symport.deps import runtimes as rt
from symport.sis import reader, writer
from tests.helpers import make_e32

E52 = {"model": "Nokia E52"}
QT = 0x2001E61C
MOBILITY = 0x2002AC89
S60_3_2 = 0x102752AE


def sis(uid, name, *, platforms=(S60_3_2,), deps=(), exe=None, dlls=None, version=(1, 0, 0), extra=None):
    files = []
    if exe is not None:
        files.append(writer.SisFile("!:\\sys\\bin\\app.exe", exe))
    for dll, data in (dlls or {}).items():
        files.append(writer.SisFile("!:\\sys\\bin\\" + dll, data))
    files += extra or []
    if not files:
        files.append(writer.SisFile("!:\\resource\\apps\\x.txt", b"x"))
    package = writer.SisPackage(uid, name, "vendor", version, files, list(platforms),
                                [writer.SisDependency(*d) for d in deps])
    return writer.build(package)


def test_reader_exposes_platform_and_dependency_items():
    raw = sis(0xE0001111, "App", deps=[(QT, "Qt", (4, 7, 3))])
    items = reader.inspect(raw)["dependencies"]["items"]
    assert items[0] == {"kind": "target-device", "uid": S60_3_2, "names": ["S60ProductID"],
                        "from_version": [0, 0, 0], "to_version": None}
    assert items[1]["kind"] == "dependency" and items[1]["names"] == ["Qt"] and items[1]["from_version"] == [4, 7, 3]
    assert reader.inspect(raw)["dependencies"]["uids_best_effort"] == [S60_3_2, QT]


def test_runtime_dependency_is_required_but_never_assumed_installed():
    result = analyze_package(sis(0xE0001111, "App", deps=[(QT, "Qt", (4, 7, 3))]), name="app.sis", target=E52)
    assert result["platform_verdict"] == "supported-static"
    assert result["declared"][0]["runtime"] == "qt" and result["declared"][0]["status"] == "required-unverified"
    assert result["runtimes"][0]["status"] == "required-unverified"
    assert result["verdict"] == "unresolved"
    assert {"dependency-unverified", "runtime-required-unverified"} <= set(result["issues"])
    assert result["levels"]["installation"] == "not-tested" and result["levels"]["physical_device"] == "not-tested"


def test_no_target_model_keeps_platform_unknown():
    result = analyze_package(sis(0xE0001111, "App"), name="a.sis", target={})
    assert result["platform_verdict"] == "unknown" and "platform-target-unknown" in result["issues"]
    assert result["verdict"] == "unresolved"


def test_unsupported_platform_blocks():
    result = analyze_package(sis(0xE0001111, "App", platforms=(0x20022E6D, 0x2003A678)), name="a.sis", target=E52)
    assert result["platform_verdict"] == "unsupported" and result["verdict"] == "blocked"
    assert all(p["relation"] == "not-accepted-by-target" for p in result["platforms"])


def test_undeclared_platform_is_unknown_not_supported():
    result = analyze_package(sis(0xE0001111, "App", platforms=()), name="a.sis", target=E52)
    assert result["platform_verdict"] == "unknown" and "platform-undeclared" in result["issues"]


def test_provided_runtime_satisfies_declared_dependency_by_uid():
    app = sis(0xE0001111, "App", deps=[(QT, "Qt", (4, 7, 3))])
    runtime = sis(QT, "Qt", version=(4, 7, 3))
    from symport.deps import provided_summary
    result = analyze_package(app, name="a.sis", target=E52, provided=[provided_summary(runtime)])
    assert result["declared"][0]["status"] == "provided-by-bundle"
    assert result["declared"][0]["matched_package"]["basis"] == "uid"
    assert result["runtimes"][0]["status"] == "provided-by-bundle"


def test_too_old_runtime_blocks_and_name_match_is_labelled():
    from symport.deps import provided_summary
    app = sis(0xE0001111, "App", deps=[(QT, "Qt", (4, 7, 3))])
    old = analyze_package(app, name="a.sis", target=E52, provided=[provided_summary(sis(QT, "Qt", version=(4, 6, 3)))])
    assert old["declared"][0]["status"] == "provided-version-too-old" and old["verdict"] == "blocked"
    other_uid = analyze_package(app, name="a.sis", target=E52, provided=[provided_summary(sis(0xE0002222, "Qt", version=(4, 7, 3)))])
    assert other_uid["declared"][0]["status"] == "provided-by-bundle-by-name"
    assert other_uid["declared"][0]["matched_package"]["basis"] == "name"


def test_imports_are_classified_without_inventing_firmware_facts():
    exe = make_e32(imports={"euser{00010000}[100039e5].dll": [1, 2], "QtCore{00040703}[2001e61c].dll": [5],
                            "helper.dll": [1], "mystery.dll": [9]})
    raw = sis(0xE0001111, "App", exe=exe, dlls={"helper.dll": make_e32(dll=True)})
    result = analyze_package(raw, name="a.sis", target=E52)
    status = {s["dll"]: s["status"] for s in result["system_imports"]}
    assert status["helper.dll"] == "package-provided"
    assert status["qtcore.dll"] == "runtime-required-unverified"
    assert status["euser.dll"] == status["mystery.dll"] == "unknown-no-firmware-data"
    assert [r["id"] for r in result["runtimes"]] == ["qt"]
    with_firmware = analyze_package(raw, name="a.sis", target=E52, firmware_dlls={"euser.dll"}, firmware_source="test")
    status = {s["dll"]: s["status"] for s in with_firmware["system_imports"]}
    assert status["euser.dll"] == "firmware-profile-present" and status["mystery.dll"] == "firmware-profile-missing"
    assert with_firmware["verdict"] == "blocked" and "system-dll-missing" in with_firmware["issues"]


def test_compressed_image_means_imports_unknown_not_empty():
    exe = make_e32(compression=0x101F7AFC)
    result = analyze_package(sis(0xE0001111, "App", exe=exe), name="a.sis", target=E52)
    assert "imports-undecoded" in result["issues"] and result["system_imports"] == []
    assert result["binaries"][0]["imports"] is None and result["verdict"] == "unresolved"


def test_capabilities_and_graph():
    exe = make_e32(caps_low=(1 << 13) | (1 << 11))  # NetworkServices + AllFiles
    result = analyze_package(sis(0xE0001111, "App", exe=exe, deps=[(QT, "Qt", (4, 7, 3))]), name="a.sis", target=E52)
    assert result["capabilities"] == ["AllFiles", "NetworkServices"] and result["restricted_capabilities"] == ["AllFiles"]
    assert "restricted-capabilities" in result["issues"]
    ids = {n["id"] for n in result["graph"]["nodes"]}
    assert {"pkg:a.sis", "plat:0x102752ae", "dep:0x2001e61c", "rt:qt"} <= ids
    assert all(e["from"] in ids | {e["from"]} for e in result["graph"]["edges"])


def test_python_payload_hint_marks_pys60_unverified():
    raw = sis(0xE0001111, "Script", extra=[writer.SisFile("!:\\data\\python\\main.py", b"print(1)")])
    result = analyze_package(raw, name="a.sis", target=E52)
    assert [r["id"] for r in result["runtimes"]] == ["pys60"] and result["runtimes"][0]["via"] == ["payload-hint"]


def test_runtime_name_tables():
    assert rt.runtime_for_name("Qt") == "qt" and rt.runtime_for_name("Qt Mobility") == "qt-mobility"
    assert rt.runtime_for_name("Python_2.0.0") == "pys60" and rt.runtime_for_name("Open C LIBC") == "open-c"
    assert rt.runtime_for_name("S60ProductID") is None
    assert rt.runtime_for_import("QtCore{00040703}[2001e61c].dll") == "qt"
    assert rt.runtime_for_import("libc.dll") == "open-c" and rt.runtime_for_import("euser.dll") is None
    assert rt.platform(0x102752AE)["symbian"] == "9.3"


def kit_parts():
    qt = sis(QT, "Qt", version=(4, 7, 3))
    mobility = sis(MOBILITY, "Qt Mobility", deps=[(QT, "Qt", (4, 7, 0))], version=(1, 2, 0))
    app = sis(0xE0001111, "App", deps=[(MOBILITY, "Qt Mobility", (1, 1, 0)), (QT, "Qt", (4, 7, 3))])
    return app, qt, mobility


def test_bundle_orders_runtimes_before_application_and_packs_zip():
    app, qt, mobility = kit_parts()
    result = build_bundle("app.sis", app, [("mobility.sis", mobility), ("qt.sis", qt)], target=E52)
    assert result["status"] == "complete" and result["unresolved"] == []
    assert [e["name"] for e in result["order"]] == ["Qt", "Qt Mobility", "App"]
    assert [e["role"] for e in result["order"]] == ["runtime", "runtime", "application"]
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(result["zip"])))
    assert archive.namelist()[:3] == ["01-qt.sis", "02-mobility.sis", "03-app.sis"]
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["levels"]["installation"] == "not-tested" and manifest["order"][2]["role"] == "application"
    assert "Install the runtime packages first" in archive.read("INSTALL.txt").decode()
    assert result["zip_name"] == "app-kit.zip"
    assert result == build_bundle("app.sis", app, [("mobility.sis", mobility), ("qt.sis", qt)], target=E52)


def test_incomplete_bundle_is_reported_and_not_packed_by_default():
    app, _qt, mobility = kit_parts()
    result = build_bundle("app.sis", app, [("mobility.sis", mobility)], target=E52)
    assert result["status"] == "incomplete" and result["zip"] is None
    assert any(u["name"] == "Qt" for u in result["unresolved"])
    forced = build_bundle("app.sis", app, [("mobility.sis", mobility)], target=E52, allow_incomplete=True)
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(forced["zip"])))
    assert "INCOMPLETE" in archive.read("INSTALL.txt").decode()


def test_bundle_reports_unused_runtime_and_rejects_bad_input():
    app, qt, mobility = kit_parts()
    extra = sis(0xE0003333, "Unrelated")
    result = build_bundle("app.sis", app, [("qt.sis", qt), ("mobility.sis", mobility), ("extra.sis", extra)], target=E52)
    assert result["unused_runtimes"] == ["extra.sis"]
    with pytest.raises(ValueError, match="SIS/SISX"):
        build_bundle("app.sis", app, [("qt.jar", qt)])
    with pytest.raises(ValueError, match="Duplicate"):
        build_bundle("app.sis", app, [("app.sis", qt)])
    with pytest.raises(ValueError):
        build_bundle("app.sis", app, [("x.sis", b"not a package")])


def test_dependency_cycle_is_rejected():
    a = sis(0xE0000001, "A", deps=[(0xE0000002, "B", (1, 0, 0))])
    b = sis(0xE0000002, "B", deps=[(0xE0000001, "A", (1, 0, 0))])
    app = sis(0xE0001111, "App", deps=[(0xE0000001, "A", (1, 0, 0))])
    with pytest.raises(ValueError, match="cycle"):
        build_bundle("app.sis", app, [("a.sis", a), ("b.sis", b)])
