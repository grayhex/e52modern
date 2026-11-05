"""Nokia N95 Reborn Hybrid CFW alpha wizard (#35): preflight, import, pin, consents, honest outcome."""
import base64

import pytest

from symport.phone import DeviceManager
from symport.revive import ReviveService
from tests.helpers import make_e32
from tests.test_deps import sis
from tests.test_revive import b64, phone
from tests.test_safety import SafetyPhone

FP1 = 0x102032BE
N95 = {"model": "Nokia N95-1", "rm": "RM-159"}


def kit(extra_resource=True, name="Reborn"):
    from symport.sis import writer

    extra = [writer.SisFile("!:\\resource\\apps\\reborn.rsc", b"rsc")] if extra_resource else []
    return sis(0xE0009999, name, platforms=(FP1,), exe=make_e32(imports={"euser.dll": [1]}), extra=extra)


def setup(tmp_path, **kw):
    transport = SafetyPhone(**{**N95, **kw})
    svc = ReviveService(tmp_path, DeviceManager(tmp_path, transport))
    return svc, transport


def imported(svc, raw=None, name="Reborn_hybrid_CFW.sis"):
    raw = raw or kit()
    result = svc.execute({"action": "reborn-import", "device": "usb", "name": name, "content": b64(raw)})
    return raw, result


def pin(svc, digest):
    return svc.execute({"action": "reborn-pin", "sha256": digest, "confirm": True})


def acks(svc, plan_id):
    view = svc.execute({"action": "safety-view", "plan": plan_id})
    codes = [b["code"] for b in view["blocking"] if b["satisfied_by"] == "acknowledgement"]
    if codes:
        svc.execute({"action": "safety-ack", "plan": plan_id, "codes": codes, "confirm": True})
    return codes


def prepare(svc):
    """Everything the user must do before a copy; returns the plan id."""
    raw, result = imported(svc)
    pin(svc, result["sha256"])
    svc.execute({"action": "reborn-backup", "device": "usb", "confirm": True})
    svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "device", "confirm": True})
    plan = svc.execute({"action": "safety-plan", "scenario": "reborn-n95", "device": "usb", "sha256": result["sha256"]})
    return raw, plan


def test_card_is_honest_about_source_licence_and_alpha(tmp_path):
    svc, _ = setup(tmp_path)
    state = svc.execute({"action": "reborn-state", "device": "usb"})
    card = state["card"]
    assert card["version"] == "v1.00 alpha" and card["release_date"] is None and card["changelog"] is None
    assert card["author_page"] == "https://avalibeyaz.com/s60" and card["author"] == "symbuzzer"
    assert card["distribution"]["status"] == "unconfirmed" and card["pinned_artifacts"] == []
    assert "not a Phoenix flash" in card["not_a_flash"]["en"]
    assert any("alpha" in w.lower() for w in card["warnings"]) and any("No uninstall" in w for w in card["warnings"])
    assert "download" not in svc.reborn.__class__.__dict__ and "fetch" not in svc.reborn.__class__.__dict__
    with pytest.raises(ValueError, match="Unknown Revive operation"):
        svc.execute({"action": "reborn-fetch", "device": "usb"})


@pytest.mark.parametrize("kw,code", [
    ({"model": "Nokia E52", "rm": None}, "not-an-n95"),
    ({"model": "N95 8GB", "rm": "RM-320"}, "n95-8gb-unproven"),
    ({"model": "N95", "rm": "RM-999"}, "variant-unknown-or-conflicting"),
    ({"model": "Nokia N95", "rm": None}, "variant-unknown-or-conflicting"),
    ({"model": "N95-2", "rm": "RM-159"}, "variant-unknown-or-conflicting"),
    ({"model": "N95-1", "rm": None}, "rm-not-reported"),
])
def test_unknown_or_unproven_variants_are_blocked(tmp_path, kw, code):
    svc, _ = setup(tmp_path, **kw)
    variant = svc.execute({"action": "reborn-state", "device": "usb"})["variant"]
    assert variant["status"] == "blocked" and variant["code"] == code


def test_known_n95_is_only_a_candidate_never_verified(tmp_path):
    svc, _ = setup(tmp_path)
    variant = svc.execute({"action": "reborn-state", "device": "usb"})["variant"]
    assert variant["status"] == "candidate" and "not a verified match" in variant["reason"]["en"]


def test_n95_8gb_stays_blocked_without_evidence_and_manual_input_never_unlocks(tmp_path):
    svc, _ = setup(tmp_path, model=None, rm=None, firmware=None)
    state = svc.execute({"action": "reborn-state", "device": "usb", "manual": {"model": "Nokia N95-1", "rm": "RM-159", "firmware": "v1"}})
    assert state["variant"]["code"] == "model-not-read-from-device"
    manual_plan_blockers = svc.reborn.variant(svc.facts(svc._row("usb")[0], {"model": "N95-1", "rm": "RM-159", "firmware": "v1"}))
    assert manual_plan_blockers["status"] == "blocked"


def test_import_validates_and_previews_without_claiming_compatibility(tmp_path):
    svc, _ = setup(tmp_path)
    raw, result = imported(svc)
    assert result["name_matches"] and result["structure"]["controller_crc_ok"] is True
    assert result["platform_verdict"] in ("supported-static", "unknown")
    assert any(f["target"].endswith("reborn.rsc") and f["high_risk"] for f in result["files"])
    assert result["high_risk_count"] >= 2 and result["known_author_hash"] is None
    assert result["pinned"] is False and "Static analysis only" in result["statement"]
    for bad in (b"", b"not a sis", b"\x00" * 200):
        with pytest.raises(ValueError, match="broken-package"):
            svc.execute({"action": "reborn-import", "device": "usb", "name": "x.sis", "content": b64(bad)})
    with pytest.raises(ValueError, match="broken-package"):
        svc.execute({"action": "reborn-import", "device": "usb", "name": "x.sis", "content": "***"})
    _, other = imported(svc, kit(False, "Other"), name="other.sis")
    assert other["name_matches"] is False


def test_pin_needs_confirmation_and_an_imported_file_and_hash_mismatch_blocks_the_plan(tmp_path):
    svc, phone_ = setup(tmp_path)
    _, result = imported(svc)
    with pytest.raises(ValueError, match="Confirm"):
        svc.execute({"action": "reborn-pin", "sha256": result["sha256"]})
    with pytest.raises(ValueError, match="Import the file first"):
        svc.execute({"action": "reborn-pin", "sha256": "0" * 64, "confirm": True})
    with pytest.raises(ValueError, match="pin the file first"):
        svc.execute({"action": "safety-plan", "scenario": "reborn-n95", "device": "usb", "sha256": result["sha256"]})
    assert pin(svc, result["sha256"])["source"] == "user-confirmed"
    _, other = imported(svc, kit(False, "Different"), name="Reborn_hybrid_CFW.sis")
    assert other["differs_from_pin"] is True
    with pytest.raises(ValueError, match="hash-differs-from-pin"):
        svc.execute({"action": "safety-plan", "scenario": "reborn-n95", "device": "usb", "sha256": other["sha256"]})
    assert phone_.uploads == 0


def test_no_backup_or_no_rights_blocks_the_transfer_with_a_clear_reason(tmp_path):
    svc, phone_ = setup(tmp_path)
    _, result = imported(svc)
    pin(svc, result["sha256"])
    plan = svc.execute({"action": "safety-plan", "scenario": "reborn-n95", "device": "usb", "sha256": result["sha256"]})
    codes = {b["code"] for b in plan["blocking"]}
    assert {"gate-no-backup", "gate-rights"} <= codes
    assert plan["risk"]["level"] == "high" and plan["risk"]["irreversible"] is True
    svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})
    acks(svc, plan["id"])
    with pytest.raises(ValueError, match="gate-no-backup"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    svc.execute({"action": "reborn-backup", "device": "usb", "confirm": True})
    with pytest.raises(ValueError, match="gate-rights"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "memory-card", "confirm": True})
    with pytest.raises(ValueError, match="gate-rights"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert phone_.uploads == 0


def test_high_risk_consents_are_separate_and_all_required(tmp_path):
    svc, phone_ = setup(tmp_path)
    raw, plan = prepare(svc)
    codes = {b["code"] for b in plan["blocking"] if b["satisfied_by"] == "acknowledgement"}
    assert codes == {"alpha-software", "irreversible-no-uninstall", "variant-not-stated-by-author", "high-risk-components"}
    svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})
    with pytest.raises(ValueError, match="Blocked"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    svc.execute({"action": "safety-ack", "plan": plan["id"], "codes": ["alpha-software"], "confirm": True})
    with pytest.raises(ValueError, match="irreversible-no-uninstall"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert phone_.uploads == 0


def test_regional_variant_needs_its_own_consent(tmp_path):
    svc, _ = setup(tmp_path, model="Nokia N95", rm="RM-160")
    _, plan = prepare(svc)
    assert "regional-variant" in {b["code"] for b in plan["blocking"]}


def test_copy_is_not_installation_and_success_needs_user_confirmation(tmp_path):
    svc, phone_ = setup(tmp_path)
    raw, plan = prepare(svc)
    svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})
    acks(svc, plan["id"])
    done = svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert done["status"] == "transferred-awaiting-manual-install"
    assert phone_.files["SymPort-Reborn/Reborn_hybrid_CFW.sis"] == raw
    assert svc.execute({"action": "reborn-state", "device": "usb"})["stages"] == {}
    with pytest.raises(ValueError):
        svc.execute({"action": "reborn-stage", "device": "usb", "stage": "installed", "result": "pass"})
    with pytest.raises(ValueError):
        svc.execute({"action": "reborn-stage", "device": "usb", "stage": "magic", "result": "pass", "confirm": True})
    assert svc.execute({"action": "reborn-stage", "device": "usb", "stage": "installer-opened", "result": "pass", "confirm": True})["success"] == "not-confirmed"
    assert svc.execute({"action": "reborn-stage", "device": "usb", "stage": "installed", "result": "pass", "confirm": True})["success"] == "installed-reported-unchecked"
    final = svc.execute({"action": "reborn-stage", "device": "usb", "stage": "network-works", "result": "pass", "confirm": True})
    assert final["success"] == "installed-reported" and final["stages"]["installed"]["source"] == "manual"
    failed = svc.execute({"action": "reborn-stage", "device": "usb", "stage": "installed", "result": "fail", "confirm": True})
    assert failed["success"] == "failed-reported"


def test_rollback_removes_only_the_copied_sis_and_never_claims_a_restore(tmp_path):
    svc, phone_ = setup(tmp_path)
    raw, plan = prepare(svc)
    svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})
    acks(svc, plan["id"])
    svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    result = svc.execute({"action": "safety-rollback", "plan": plan["id"], "confirm": True})
    assert result["removed"] == ["SymPort-Reborn/Reborn_hybrid_CFW.sis"] and result["system_restored"] is False
    assert result["installed_software"] == "not-restored"
    assert not phone_.files


def test_plan_from_one_phone_is_refused_on_another_phone_or_firmware(tmp_path):
    svc, phone_ = setup(tmp_path)
    raw, plan = prepare(svc)
    svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})
    acks(svc, plan["id"])
    phone_.row = phone(model="N95 8GB", rm="RM-320")
    with pytest.raises(ValueError, match="no longer matches"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    phone_.row = phone(**N95, firmware="other firmware")
    with pytest.raises(ValueError, match="firmware-changed"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert phone_.uploads == 0


def test_no_network_is_ever_used(tmp_path, monkeypatch):
    import socket

    def deny(*a, **k):
        raise AssertionError("the Reborn wizard must not touch the network")

    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    svc, _ = setup(tmp_path)
    raw, plan = prepare(svc)
    assert plan["items"][0]["sha256"] and base64.b64decode(b64(raw)) == raw


def kit_with(*targets, version=(1, 0, 0)):
    from symport.sis import writer
    from tests.test_deps import S60_3_2  # noqa: F401

    files = [writer.SisFile(t, b"x") for t in targets]
    return writer.build(writer.SisPackage(0xE0009998, "Reborn", "v", version, files, [FP1], []))


def test_modifications_come_from_file_names_and_never_confirm_behaviour(tmp_path):
    svc, _ = setup(tmp_path)
    raw = kit_with("!:\\resource\\cacerts\\mozilla.cer", "!:\\private\\10202be9\\uaprof.rdf", "!:\\sys\\bin\\ngage_lib.dll")
    _, result = imported(svc, raw)
    mods = {m["category"]: m for m in result["modifications"]}
    assert mods["ssl-ca"]["status"] == "present-by-file-name" and mods["uaprof"]["status"] == "present-by-file-name"
    assert mods["n-gage"]["status"] == "present-by-file-name"
    assert mods["connectivity-check"]["status"] == "not-detected" and mods["file-manager"]["status"] == "not-detected"
    assert all(m["confirmed_behaviour"] is False and m["basis"] == "file-name-pattern" for m in mods.values())
    assert result["version_check"]["status"] == "matches-author-claim" and result["version_check"]["package"] == "1.0.0"
    other = imported(svc, kit_with("!:\\resource\\x.txt", version=(2, 3, 0)), name="x.sis")[1]
    assert other["version_check"]["status"] == "differs-from-author-claim"


def test_overlap_with_the_tls_stack_needs_its_own_consent_and_shows_tls_state(tmp_path):
    svc, _ = setup(tmp_path)
    raw = kit_with("!:\\sys\\bin\\ssl.dll", "!:\\resource\\apps\\x.txt")
    _, result = imported(svc, raw)
    assert result["tls_overlap"] == ["!:\\sys\\bin\\ssl.dll"] and result["tls_state"]["ssl-patch"] == "unknown"
    svc.execute({"action": "tls-record", "device": "usb", "item": "ssl-patch", "state": "installed", "confirm": True})
    _, result = imported(svc, raw)
    assert result["tls_state"]["ssl-patch"] == "installed-reported"
    pin(svc, result["sha256"])
    plan = svc.execute({"action": "safety-plan", "scenario": "reborn-n95", "device": "usb", "sha256": result["sha256"]})
    overlap = [b for b in plan["blocking"] if b["code"] == "tls-stack-overlap"]
    assert overlap and "ssl-patch=installed-reported" in overlap[0]["text"]["en"]
    clean = kit_with("!:\\resource\\apps\\x.txt")
    _, r2 = imported(svc, clean, name="clean.sis")
    assert r2["tls_overlap"] == []


def test_postchecks_are_user_reported_with_an_evidence_level(tmp_path):
    svc, _ = setup(tmp_path)
    state = svc.execute({"action": "reborn-state", "device": "usb"})
    assert state["postcheck_items"] == ["calls-sms", "file-manager", "wifi", "https-on-phone", "alt-links", "launch-uninstall"]
    out = svc.execute({"action": "reborn-stage", "device": "usb", "stage": "https-on-phone", "result": "fail", "confirm": True})
    assert out["stages"]["https-on-phone"]["evidence"] == "user-reported"
    assert out["success"] == "not-confirmed"  # a post-check never turns into an installation claim
    assert svc.execute({"action": "reborn-state", "device": "usb"})["postchecks"]["https-on-phone"]["result"] == "fail"


def test_format_is_never_presented_as_a_reliable_rollback(tmp_path):
    svc, _ = setup(tmp_path)
    warnings = svc.execute({"action": "reborn-state", "device": "usb"})["card"]["warnings"]
    assert any("NOT a reliable rollback" in w for w in warnings)
