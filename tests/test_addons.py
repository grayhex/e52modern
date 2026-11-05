"""Add-ons & Patch Manager (#39): gated plans, closed system patches, manual inventory, honest levels."""
import hashlib

import pytest

from symport.phone import DeviceManager
from symport.revive import ReviveService
from symport.revive.addons import load
from tests.test_deps import sis
from tests.test_revive import b64, phone
from tests.test_safety import SafetyPhone

REGISTRY = load()


def setup(tmp_path, **kw):
    transport = SafetyPhone(**kw)
    return ReviveService(tmp_path, DeviceManager(tmp_path, transport)), transport


def plan(svc, addon, action="install"):
    return svc.execute({"action": "addons-plan", "device": "usb", "addon": addon, "action_kind": action})


def codes(result):
    return {b["code"] for b in result["blocks"]}


def test_registry_is_consistent_and_system_patches_are_closed_by_default():
    assert REGISTRY["categories"]["system-patch"]["closed_by_default"] is True
    assert {a["id"] for a in REGISTRY["addons"]} == {"tls-mbedtls", "tls-ssl-patch", "reborn-hybrid-n95", "rompatcher-debloated", "homepage-setting"}
    debloated = next(a for a in REGISTRY["addons"] if a["id"] == "rompatcher-debloated")
    assert debloated["licence"]["spdx"] is None and debloated["targets"] == [] and debloated["component_ref"] is None


def test_unknown_or_wrong_models_block_every_add_on(tmp_path):
    svc, phone_ = setup(tmp_path, model="N95-2", rm="RM-159")
    assert "model-unidentified" in codes(plan(svc, "tls-mbedtls"))
    phone_.row = phone(model=None, firmware=None)
    assert "model-unidentified" in codes(plan(svc, "homepage-setting"))
    phone_.row = phone(model="Nokia N95-1", rm=None)
    assert "rm-unknown" in codes(plan(svc, "tls-mbedtls"))
    phone_.row = phone()  # E52 is not a target of the N95-only Reborn kit
    assert "model-not-targeted" in codes(plan(svc, "reborn-hybrid-n95"))


def test_medium_risk_add_on_is_only_prepared_never_installed(tmp_path):
    svc, _ = setup(tmp_path)
    result = plan(svc, "tls-mbedtls")
    assert result["decision"] == "ready-to-prepare" and result["dry_run"] is True
    assert "firmware-not-verified" in result["warnings"] and "never installs" in result["statement"]
    assert result["levels"] == {"downloaded": False, "transferred": False, "user-confirmed-installed": False, "verified-on-device": "not-available"}
    with pytest.raises(ValueError, match="Obtain the pinned file"):
        svc.execute({"action": "addons-prepare", "device": "usb", "addon": "tls-mbedtls"})


def test_prepare_uses_the_safety_net_and_tracks_levels(tmp_path):
    svc, phone_ = setup(tmp_path)
    raw = sis(0xE0001234, "Synthetic MBedTLS")
    spec = dict(svc.tls.components["mbedtls-lib"], size=len(raw), sha256=hashlib.sha256(raw).hexdigest(), package={"uid": "0xe0001234", "signed": False, "targets": []})
    svc.tls.components = dict(svc.tls.components, **{"mbedtls-lib": spec})
    svc.execute({"action": "tls-import", "name": "MBedTLS.sis", "content": b64(raw)})
    prepared = svc.execute({"action": "addons-prepare", "device": "usb", "addon": "tls-mbedtls"})
    assert prepared["scenario"] == "tls" and prepared["status"] == "planned"
    svc.execute({"action": "safety-snapshot", "plan": prepared["id"], "confirm": True})
    svc.execute({"action": "safety-apply", "plan": prepared["id"], "confirm": True})
    state = svc.execute({"action": "addons-state", "device": "usb"})
    item = {a["id"]: a for a in state["addons"]}["tls-mbedtls"]
    assert item["levels"]["downloaded"] and item["levels"]["transferred"]
    assert item["levels"]["user-confirmed-installed"] is False and item["levels"]["verified-on-device"] == "not-available"
    svc.execute({"action": "addons-mark", "device": "usb", "addon": "tls-mbedtls", "state": "installed", "confirm": True})
    state = svc.execute({"action": "addons-state", "device": "usb"})
    assert {a["id"]: a for a in state["addons"]}["tls-mbedtls"]["levels"]["user-confirmed-installed"] is True
    assert phone_.files["SymPort-TLS/MBedTLS.sis"] == raw


def test_system_patches_stay_blocked_until_every_gate_is_met(tmp_path):
    svc, _ = setup(tmp_path, model="Nokia N95-1", rm="RM-159")
    first = plan(svc, "reborn-hybrid-n95")
    assert {"category-closed", "version-unconfirmed", "licence-missing", "firmware-unverified", "privileges-missing", "incomplete-backup"} <= codes(first)
    assert first["decision"] == "blocked"
    with pytest.raises(ValueError, match="acknowledge"):
        svc.execute({"action": "addons-open-category", "device": "usb", "category": "system-patch", "confirm": True})
    with pytest.raises(ValueError, match="closed categories"):
        svc.execute({"action": "addons-open-category", "device": "usb", "category": "settings", "confirm": True, "acknowledge": True})
    svc.execute({"action": "addons-open-category", "device": "usb", "category": "system-patch", "confirm": True, "acknowledge": True})
    svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "memory-card", "confirm": True})
    second = plan(svc, "reborn-hybrid-n95")
    assert "category-closed" not in codes(second) and "privileges-missing" in codes(second)
    svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "device", "confirm": True})
    svc.execute({"action": "reborn-backup", "device": "usb", "confirm": True})
    third = plan(svc, "reborn-hybrid-n95")
    assert not ({"privileges-missing", "incomplete-backup"} & codes(third))
    assert third["decision"] == "blocked"  # licence, version and firmware are still unconfirmed


def test_dependencies_conflicts_and_autostart_conflicts_are_enforced(tmp_path):
    svc, _ = setup(tmp_path)
    assert "dependency-missing:tls-mbedtls" in codes(plan(svc, "tls-ssl-patch"))
    svc.execute({"action": "addons-mark", "device": "usb", "addon": "tls-mbedtls", "state": "installed", "confirm": True})
    assert "dependency-missing:tls-mbedtls" not in codes(plan(svc, "tls-ssl-patch"))
    svc.execute({"action": "addons-mark", "device": "usb", "addon": "reborn-hybrid-n95", "state": "installed", "confirm": True})
    assert "conflict:reborn-hybrid-n95" in codes(plan(svc, "tls-ssl-patch"))
    svc.execute({"action": "patch-save", "device": "usb", "name": "Other patch", "state": "autostart", "autostart_via": "domainsrv"})
    assert "autostart-conflict" in codes(plan(svc, "rompatcher-debloated"))


def test_unlicensed_unversioned_research_entry_is_never_automatable(tmp_path):
    svc, _ = setup(tmp_path)
    result = plan(svc, "rompatcher-debloated")
    assert result["decision"] == "blocked" and {"licence-missing", "version-unconfirmed", "model-not-targeted"} <= codes(result)
    with pytest.raises(ValueError, match="Not preparable"):
        svc.execute({"action": "addons-prepare", "device": "usb", "addon": "rompatcher-debloated"})
    item = {a["id"]: a for a in svc.execute({"action": "addons-state", "device": "usb"})["addons"]}["rompatcher-debloated"]
    assert item["mode"] == "manual-only" and "not proof that it is safe" in item["install"]["en"]


def test_hash_mismatch_blocks_a_substituted_file(tmp_path):
    svc, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="hash-mismatch"):
        svc.execute({"action": "addons-verify-file", "addon": "tls-mbedtls", "content": b64(b"not the pinned build")})
    pinned = svc.execute({"action": "addons-verify-file", "addon": "rompatcher-debloated", "content": b64(b"anything")})
    assert pinned["status"] == "cannot-verify" and pinned["sha256"] == hashlib.sha256(b"anything").hexdigest()
    with pytest.raises(ValueError, match="broken-package"):
        svc.execute({"action": "addons-verify-file", "addon": "tls-mbedtls", "content": "***"})


def test_removal_is_manual_and_never_promises_a_system_restore(tmp_path):
    svc, _ = setup(tmp_path)
    result = plan(svc, "tls-ssl-patch", "remove")
    assert result["decision"] == "manual-only" and "cannot remove" in result["statement"] and "SymPort cannot restore a system DLL" in result["rollback"]["en"]
    with pytest.raises(ValueError, match="Invalid action"):
        plan(svc, "tls-mbedtls", "wipe")


def test_patch_inventory_is_manual_validated_and_read_only_for_the_phone(tmp_path):
    svc, phone_ = setup(tmp_path)
    state = svc.execute({"action": "addons-state", "device": "usb"})
    assert state["patch_manager"]["agent_inventory"] == "not-available" and state["patch_manager"]["writes"] == "disabled"
    for bad in ({"name": "", "state": "applied"}, {"name": "x", "state": "running"}, {"name": "x", "state": "applied", "original_sha256": "xyz"}):
        with pytest.raises(ValueError):
            svc.execute({"action": "patch-save", "device": "usb", **bad})
    first = svc.execute({"action": "patch-save", "device": "usb", "name": "Patch A", "state": "autostart", "autostart_via": "domainsrv",
                         "depends_on": ["Patch Z"], "original_sha256": "a" * 64})["patch"]
    svc.execute({"action": "patch-save", "device": "usb", "name": "Patch B", "state": "autostart", "autostart_via": "domainsrv"})
    svc.execute({"action": "patch-save", "device": "usb", "name": "Patch C", "state": "unknown"})
    warnings = svc.execute({"action": "addons-state", "device": "usb"})["patch_warnings"]
    assert {"autostart-conflict", "dependency-missing", "state-unknown"} <= {w["code"] for w in warnings}
    phone_.row = phone(firmware="v 999")
    assert "recorded-for-other-firmware" not in {w["code"] for w in svc.execute({"action": "addons-state", "device": "usb"})["patch_warnings"]}  # other phone: not shown at all
    phone_.row = phone()
    with pytest.raises(ValueError, match="Confirm"):
        svc.execute({"action": "patch-delete", "device": "usb", "id": first["id"]})
    svc.execute({"action": "patch-delete", "device": "usb", "id": first["id"], "confirm": True})
    with pytest.raises(ValueError, match="Unknown inventory entry"):
        svc.execute({"action": "patch-delete", "device": "usb", "id": first["id"], "confirm": True})
    assert not [c for c in phone_.calls if c[0] in ("upload", "delete")]


def test_update_notice_prepares_nothing(tmp_path):
    svc, phone_ = setup(tmp_path)
    svc.execute({"action": "addons-mark", "device": "usb", "addon": "tls-mbedtls", "state": "installed", "confirm": True})
    key = svc._key(svc._row("usb")[0])
    saved = svc._load("observations", key)
    saved["addons"]["tls-mbedtls"]["version"] = "1.3.0"
    svc._save("observations", key, saved)
    item = {a["id"]: a for a in svc.execute({"action": "addons-state", "device": "usb"})["addons"]}["tls-mbedtls"]
    assert item["update_available"] is True
    assert phone_.uploads == 0
