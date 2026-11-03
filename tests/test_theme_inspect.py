import json
import struct

import pytest

from symport.config import Config
from symport.report import FAIL
from symport.theme import inspect as tinspect
from tests.helpers import repo_copy

VARIANTS = ("light", "dark")


def failures(rep):
    return {c.id: c.message for c in rep.checks if c.status == FAIL}


@pytest.mark.parametrize("variant", VARIANTS)
def test_committed_theme_passes_static_inspection(cfg, variant):
    rep = tinspect.inspect_variant(cfg, variant)
    assert failures(rep) == {}
    assert rep.verification == {"static_automated": True, "emulator": "not-tested", "physical_device": "not-tested"}
    ids = {c.id: c for c in rep.checks}
    # static checks must never claim firmware or device acceptance
    assert ids["firmware.acceptance"].status == "unknown" and ids["firmware.acceptance"].level == "firmware"
    assert ids["device.install"].status == "unknown" and ids["device.install"].level == "device"
    assert ids["uid.range"].status == "warn"             # test-range UID is flagged
    assert len(rep.artifacts) == 4


def test_structure_facts_regression(cfg):
    """Pinned structural facts of the existing build (counts survive rebuilds)."""
    golden = json.loads((cfg.repo / "tests" / "golden" / "theme-structure.json").read_text())
    for v in VARIANTS:
        rep = tinspect.inspect_variant(cfg, v)
        ev = {c.id: c.evidence for c in rep.checks}
        assert ev["mbm.structure"]["bitmaps"] == golden[v]["mbm_bitmaps"]
        assert ev["mif.structure"]["icons"] == golden[v]["mif_icons"]
        assert rep.data["package"]["uid"] == golden[v]["uid"]
        assert rep.data["package"]["files"] == golden[v]["pkg_files"]


@pytest.fixture
def broken(tmp_path):
    root = repo_copy(tmp_path / "r")
    return root, Config.load(root)


def test_missing_dist(tmp_path):
    root = repo_copy(tmp_path / "r")
    import shutil
    shutil.rmtree(root / "theme" / "dist" / "light")
    rep = tinspect.inspect_variant(Config.load(root), "light")
    assert "dist.present" in failures(rep)


def test_truncated_mbm_detected(broken):
    root, cfg = broken
    p = root / "theme" / "dist" / "light" / "e52clearlight.mbm"
    p.write_bytes(p.read_bytes()[:200])
    assert "mbm.structure" in failures(tinspect.inspect_variant(cfg, "light"))


def test_skn_length_field_corruption_detected(broken):
    root, cfg = broken
    p = root / "theme" / "dist" / "dark" / "e52cleardark.skn"
    b = bytearray(p.read_bytes())
    struct.pack_into("<I", b, 0, len(b) + 7)
    p.write_bytes(bytes(b))
    assert "skn.structure" in failures(tinspect.inspect_variant(cfg, "dark"))


def test_mif_pointing_outside_mbm_detected(broken):
    root, cfg = broken
    p = root / "theme" / "dist" / "light" / "e52clearlight.mif"
    b = bytearray(p.read_bytes())
    struct.pack_into("<i", b, 16, -9999)
    p.write_bytes(bytes(b))
    assert "mif.structure" in failures(tinspect.inspect_variant(cfg, "light"))


def test_uid_inconsistency_between_pkg_and_skn(broken):
    root, cfg = broken
    p = root / "theme" / "dist" / "light" / "e52clearlight.pkg"
    t = p.read_text().replace("0xe0e52c01", "0xe0e52c77")
    p.write_text(t)
    f = failures(tinspect.inspect_variant(cfg, "light"))
    assert "uid.consistency" in f or "pkg.paths" in f


def test_missing_platform_dependency_detected(broken):
    root, cfg = broken
    p = root / "theme" / "dist" / "dark" / "e52cleardark.pkg"
    p.write_text("\n".join(ln for ln in p.read_text().splitlines() if "0x101f7961" not in ln.lower()))
    assert "pkg.platform" in failures(tinspect.inspect_variant(cfg, "dark"))


def test_wrong_install_path_detected(broken):
    root, cfg = broken
    p = root / "theme" / "dist" / "light" / "e52clearlight.pkg"
    p.write_text(p.read_text().replace("\\resource\\skins\\", "\\resource\\wrong\\"))
    assert "pkg.paths" in failures(tinspect.inspect_variant(cfg, "light"))


def test_palette_contrast_regression_detected(broken):
    root, cfg = broken
    p = root / "theme" / "colours.json"
    d = json.loads(p.read_text())
    d["light"]["contrast"][0]["fg"] = "#EEEEEE"   # near-white text on the light background
    p.write_text(json.dumps(d))
    assert "palette.contrast" in failures(tinspect.inspect_variant(cfg, "light"))


def test_stale_manifest_status_detected(broken):
    root, cfg = broken
    p = root / "theme" / "manifest.json"
    d = json.loads(p.read_text())
    d["status"] = "ASSETS ONLY: old"
    p.write_text(json.dumps(d))
    assert "manifest.status" in failures(tinspect.inspect_variant(cfg, "light"))


def test_mbm_sources_mismatch_detected(broken):
    root, cfg = broken
    gfx = root / "theme" / "src" / "light" / "gfx" / "bg_screen.bmp"
    b = bytearray(gfx.read_bytes())
    struct.pack_into("<i", b, 18, 100)   # change declared width
    gfx.write_bytes(bytes(b))
    assert "mbm.match_sources" in failures(tinspect.inspect_variant(cfg, "light"))


def test_contrast_function_known_values():
    assert tinspect.contrast("#000000", "#FFFFFF") == 21.0
    assert tinspect.contrast("#777777", "#777777") == 1.0
