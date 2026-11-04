"""P0 integration: curated X-plore/Jellyfin entries and the Inspector's dependency/kit actions."""
from __future__ import annotations

import base64
import json
import socket
from pathlib import Path

import pytest

from symport.catalog.download import public_https
from symport.catalog.model import Catalog
from symport.web import Workbench
from tests.test_deps import E52, MOBILITY, QT, kit_parts, sis
from tests.test_firmware import firmware, upload, zip_bytes
from tests.test_web import repo  # noqa: F401

CATALOG = Catalog(Path(__file__).resolve().parents[1] / "catalog")


def b64(raw):
    return base64.b64encode(raw).decode()


def test_jellyfin_variants_use_pinned_release_assets_and_conflict():
    en, ru = CATALOG.entries["jellyfin-s60-en"], CATALOG.entries["jellyfin-s60-ru"]
    for entry, suffix in ((en, "EN"), (ru, "RU")):
        (artifact,) = CATALOG.sources[entry["source_id"]]["artifacts"]
        assert artifact["url"] == f"https://github.com/Hinduc0der/jellyfin-s60v3/releases/download/v0.3.22/jellyfin-0.3.22-{suffix}.sis"
        assert len(artifact["sha256"]) == 64 and artifact["size"] > 100_000
        assert entry["delivery"] == "automatic" and entry["compatibility"] == "untested" and entry["e52_evidence"] is None
        assert entry["runtime_requirements"] == [{"runtime": "qt", "name": "Qt", "min_version": "4.7.3",
                                                  "declared_in": "SIS controller (проверено SymPort)", "status": "unverified"}]
        assert "истёк" in entry["signature"] and entry["guide"]["steps"] and entry["license"] == "GPL-3.0"
    assert en["conflicts_with"] == ["jellyfin-s60-ru"] and ru["conflicts_with"] == ["jellyfin-s60-en"]
    plan = CATALOG.plan(["jellyfin-s60-en", "jellyfin-s60-ru"])
    assert any("share one application identity" in p for p in plan["problems"])
    single = CATALOG.plan(["jellyfin-s60-ru"])
    assert single["problems"] == [] and single["runtime_requirements"]["jellyfin-s60-ru"][0]["runtime"] == "qt"
    assert any("Qt" in r for r in single["requirements"]["jellyfin-s60-ru"])


def test_xplore_entry_is_official_download_with_pin_and_no_false_claims():
    entry = CATALOG.entries["xplore"]
    (artifact,) = CATALOG.sources["xplore"]["artifacts"]
    assert artifact["url"].startswith("https://www.lonelycatgames.com/") and artifact["size"] == 510612
    assert artifact["sha256"] == "283c9a0b952e9f959e44b0138c61397decb165fa0354bab74c54a18a73ae2d5c"
    assert entry["compatibility"] == "likely-compatible" and entry["e52_evidence"] is None and entry["format"] == "sisx"
    assert any("Visual Studio 2008" in text for text in entry["limitations"])
    assert "истёк" in entry["signature"]


def test_download_host_allow_list_covers_only_curated_hosts():
    def public(*_a, **_k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
    public_https("https://www.lonelycatgames.com/?wpdmdl=509", public)
    for url in ("https://evil.lonelycatgames.com/x", "https://lonelycatgames.com/x", "http://www.lonelycatgames.com/x",
                "https://www.lonelycatgames.com.evil.test/x"):
        with pytest.raises(ValueError):
            public_https(url, public)


def test_unknown_conflict_reference_is_rejected(tmp_path):
    root = tmp_path / "catalog"
    (root / "apps").mkdir(parents=True)
    entry = json.loads((Path(__file__).resolve().parents[1] / "catalog/apps/xplore.json").read_text())
    entry["conflicts_with"] = ["nope"]
    (root / "apps/xplore.json").write_text(json.dumps(entry))
    (root / "sources.json").write_text(json.dumps({"xplore": CATALOG.sources["xplore"]}))
    (root / "research.json").write_text("[]")
    with pytest.raises(ValueError, match="Unknown conflicting"):
        Catalog(root)


def test_inspector_dependencies_and_kit_actions(repo):  # noqa: F811
    workbench = Workbench(repo)
    app, qt, mobility = kit_parts()
    base = {"source": "upload", "name": "app.sis", "content": b64(app), "target": E52}
    report = workbench.inspector.execute({"action": "dependencies", **base})
    assert report["verdict"] == "unresolved" and {d["runtime"] for d in report["declared"]} == {"qt", "qt-mobility"}
    resolved = workbench.inspector.execute({"action": "dependencies", **base, "runtimes": [
        {"source": "upload", "name": "qt.sis", "content": b64(qt)},
        {"source": "upload", "name": "mobility.sis", "content": b64(mobility)}]})
    assert all(d["status"] == "provided-by-bundle" for d in resolved["declared"])
    kit = workbench.inspector.execute({"action": "bundle", **base, "runtimes": [
        {"source": "upload", "name": "mobility.sis", "content": b64(mobility)},
        {"source": "upload", "name": "qt.sis", "content": b64(qt)}]})
    assert kit["status"] == "complete" and [e["role"] for e in kit["order"]] == ["runtime", "runtime", "application"]
    incomplete = workbench.inspector.execute({"action": "bundle", **base})
    assert incomplete["status"] == "incomplete" and incomplete["zip"] is None
    with pytest.raises(ValueError, match="SIS/SISX"):
        workbench.inspector.execute({"action": "dependencies", "source": "upload", "name": "a.jar", "content": b64(b"x")})
    with pytest.raises(ValueError):
        workbench.inspector.execute({"action": "dependencies", **base, "runtimes": ["x"] * 13})


def test_inspector_report_carries_dependency_analysis_with_firmware_index(repo):  # noqa: F811
    workbench = Workbench(repo)
    from tests.helpers import make_e32
    exe = make_e32(imports={"euser.dll": [1], "vanished.dll": [2]})
    raw = sis(0xE0001111, "App", exe=exe, deps=[(QT, "Qt", (4, 7, 3))])
    plain = workbench.inspector.execute({"action": "analyze", "source": "upload", "name": "a.sis", "content": b64(raw),
                                         "target": {"model": "Nokia E52", "os": "9.3"}})
    assert plain["dependency_analysis"]["verdict"] == "unresolved" and plain["dependency_analysis"]["firmware"] is None
    key, _ = upload(workbench.firmware, zip_bytes(firmware()))
    informed = workbench.inspector.execute({"action": "analyze", "source": "upload", "name": "a.sis", "content": b64(raw),
                                            "target": {"model": "Nokia E52", "os": "9.3"}, "firmware_id": key})
    dep = informed["dependency_analysis"]
    assert dep["firmware"]["source"].startswith("firmware-explorer:")
    status = {s["dll"]: s["status"] for s in dep["system_imports"]}
    assert status == {"euser.dll": "firmware-profile-present", "vanished.dll": "firmware-profile-missing"}
    assert dep["verdict"] == "blocked"
    assert informed["compatibility"] in ("unknown", "incompatible") and informed["physical_device"] == "not-tested"
    with pytest.raises(ValueError, match="Firmware"):
        workbench.inspector.execute({"action": "analyze", "source": "upload", "name": "a.sis", "content": b64(raw),
                                     "firmware_id": "0" * 16})
    assert MOBILITY  # fixture constant is shared with test_deps
