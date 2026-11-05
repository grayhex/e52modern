"""Recovery Safety Net (#36): plans, snapshots, interrupted transfers, rollback and reports without a phone."""
import base64
import hashlib
import io
import json
import zipfile

import pytest

from symport.phone import DeviceManager
from symport.revive import ReviveService
from tests.test_deps import sis
from tests.test_revive import b64, phone


class SafetyPhone:
    """In-memory phone: list/mkdir/upload/download/delete plus fault injection."""

    def __init__(self, **kw):
        self.kw = kw
        self.row = phone(**kw)
        self.files = {}
        self.calls = []
        self.fail_upload_at = None  # 1-based number of the upload that raises
        self.corrupt = False
        self.uploads = 0
        self.present = True

    def devices(self):
        return [dict(self.row)] if self.present else []

    def execute(self, data):
        a, path = data["action"], data.get("path", "")
        self.calls.append((a, path))
        if a == "mkdir":
            return {}
        if a == "list":
            names = [p.split("/", 1)[1] for p in self.files if p.startswith(path + "/")]
            if not names and not any(p.startswith(path + "/") for p in self.files):
                raise ValueError("no such folder")
            return {"entries": [{"name": n, "directory": False, "size": len(self.files[path + "/" + n])} for n in names]}
        if a == "upload":
            self.uploads += 1
            if self.fail_upload_at == self.uploads:
                raise OSError("link dropped")
            if path in self.files:
                raise FileExistsError(path)
            raw = base64.b64decode(data["content"])
            self.files[path] = raw[:-1] + b"X" if self.corrupt else raw
            return {"status": "verified"}
        if a == "download":
            if path not in self.files:
                raise ValueError("missing")
            return {"content": base64.b64encode(self.files[path]).decode()}
        if a == "delete":
            del self.files[path]
            return {}
        if a == "contacts-read":
            return {"contacts": [{"name": "Private Person", "tel": "+100000"}]}
        if a == "apps-inventory":
            return {"packages": [{"name": "a.sis"}]}
        raise AssertionError(data)


def setup(tmp_path, **kw):
    transport = SafetyPhone(**kw)
    svc = ReviveService(tmp_path, DeviceManager(tmp_path, transport))
    raw = sis(0xE0001234, "Synthetic MBedTLS")
    spec = dict(svc.tls.components["mbedtls-lib"], size=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                package={"uid": "0xe0001234", "signed": False, "targets": []})
    svc.tls.components = dict(svc.tls.components, **{"mbedtls-lib": spec})
    svc.execute({"action": "tls-import", "name": "MBedTLS.sis", "content": b64(raw)})
    return svc, transport, raw


def new_plan(svc, components=("mbedtls-lib",)):
    return svc.execute({"action": "safety-plan", "scenario": "tls", "device": "usb", "components": list(components)})


def ready(svc, plan):
    svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})
    return plan["id"]


def test_plan_is_a_dry_run_bound_to_the_phone_and_files(tmp_path):
    svc, phone_, raw = setup(tmp_path)
    plan = new_plan(svc)
    assert plan["status"] == "planned" and plan["dry_run"]["new_files"] == 1 and plan["dry_run"]["conflicts"] == []
    assert plan["binding"]["rm"] is None and plan["binding"]["firmware"] == phone_.row["firmware"]
    assert plan["binding"]["files"] == [hashlib.sha256(raw).hexdigest()]
    assert not phone_.files and not [c for c in phone_.calls if c[0] in ("upload", "delete")]
    assert "cannot restore the phone" in plan["statement"]


def test_apply_requires_snapshot_and_confirmation_and_never_claims_install(tmp_path):
    svc, phone_, raw = setup(tmp_path)
    plan = new_plan(svc)
    with pytest.raises(ValueError, match="snapshot first"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    with pytest.raises(ValueError, match="Confirm"):
        svc.execute({"action": "safety-snapshot", "plan": plan["id"]})
    ready(svc, plan)
    with pytest.raises(ValueError, match="Confirm"):
        svc.execute({"action": "safety-apply", "plan": plan["id"]})
    done = svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert done["status"] == "transferred-awaiting-manual-install"
    assert phone_.files["SymPort-TLS/MBedTLS.sis"] == raw
    assert all(i["state"] == "written" and i["created"] for i in done["items"])
    with pytest.raises(ValueError, match="already applied"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert phone_.uploads == 1


def test_snapshot_kinds_are_honest_and_pim_only_when_verified(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    plan = new_plan(svc)
    snap = svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})["snapshot"]
    assert snap["complete_phone_backup"] is False
    assert snap["kinds"]["firmware"] == "not-available" and snap["kinds"]["card-copy"] == "not-performed"
    assert snap["kinds"]["pim-export"].startswith("not-available")
    # contacts.read verified -> exported locally, but never into the shareable report
    from tests.capfake import row
    phone_.row = row(dict(phone_.row, capability_fingerprint_seed=1), available=("identity.read", "storage.read", "files.list", "files.download", "contacts.read"),
                     untested_writes=("files.upload", "packages.transfer", "files.mkdir"))
    plan2 = new_plan(svc)
    snap2 = svc.execute({"action": "safety-snapshot", "plan": plan2["id"], "confirm": True})["snapshot"]
    assert snap2["kinds"]["pim-export"] == "done" and snap2["pim"]["count"] == 1
    exported = base64.b64decode(svc.execute({"action": "safety-export", "plan": plan2["id"]})["content"]).decode()
    assert "Private Person" not in exported and "+100000" not in exported and "imei" not in exported.lower()


def test_interrupted_transfer_is_resumable_and_rollback_removes_only_our_files(tmp_path):
    svc, phone_, raw = setup(tmp_path)
    # second planned file from a different synthetic package
    other = sis(0xE0005678, "Second")
    digest = svc.safety.put_artifact(other)
    plan = new_plan(svc)
    stored = svc.safety.load(plan["id"])
    stored["items"].append({"name": "Second.sis", "path": "SymPort-TLS/Second.sis", "sha256": digest, "size": len(other),
                            "state": "planned", "created": False, "component": None})
    stored["binding"]["files"] = sorted(stored["binding"]["files"] + [digest])
    svc.safety.save(stored)
    ready(svc, plan)
    phone_.files["SymPort-TLS/user-owned.txt"] = b"mine"
    phone_.fail_upload_at = 2
    with pytest.raises(OSError):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    interrupted = svc.safety.load(plan["id"])
    assert interrupted["status"] == "interrupted"
    assert [i["state"] for i in interrupted["items"]] == ["written", "planned"]
    # reconnect: the plan resumes without re-uploading the finished file
    phone_.fail_upload_at = None
    done = svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert done["status"] == "transferred-awaiting-manual-install" and phone_.uploads == 3
    preview = svc.execute({"action": "safety-rollback", "plan": plan["id"]})
    assert preview["dry_run"] is True and len(preview["files"]) == 2 and "system_restore" in preview
    result = svc.execute({"action": "safety-rollback", "plan": plan["id"], "confirm": True})
    assert result["status"] == "rolled-back" and result["system_restored"] is False
    assert set(phone_.files) == {"SymPort-TLS/user-owned.txt"}
    assert ("delete", "SymPort-TLS") not in phone_.calls  # never recursive


def test_rollback_keeps_files_that_changed_and_is_limited_to_our_plan(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    plan = new_plan(svc)
    ready(svc, plan)
    svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    phone_.files["SymPort-TLS/MBedTLS.sis"] = b"edited by the user"
    result = svc.execute({"action": "safety-rollback", "plan": plan["id"], "confirm": True})
    assert result["status"] == "rollback-partial" and result["conflicts"] == ["SymPort-TLS/MBedTLS.sis"]
    assert phone_.files["SymPort-TLS/MBedTLS.sis"] == b"edited by the user"


def test_existing_different_file_blocks_and_is_never_overwritten(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    phone_.files["SymPort-TLS/MBedTLS.sis"] = b"someone else"
    plan = new_plan(svc)
    assert plan["dry_run"]["conflicts"] == ["SymPort-TLS/MBedTLS.sis"]
    assert any(b["code"] == "file-conflict" for b in plan["blocking"])
    ready(svc, plan)
    with pytest.raises(ValueError, match="Blocked: file-conflict"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert phone_.files["SymPort-TLS/MBedTLS.sis"] == b"someone else" and phone_.uploads == 0


def test_file_that_appears_after_planning_is_a_conflict_not_an_overwrite(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    plan = new_plan(svc)
    ready(svc, plan)
    phone_.files["SymPort-TLS/MBedTLS.sis"] = b"appeared later"
    with pytest.raises(ValueError, match="conflict"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert phone_.files["SymPort-TLS/MBedTLS.sis"] == b"appeared later"
    assert svc.safety.load(plan["id"])["status"] == "interrupted"


def test_sha_mismatch_after_upload_is_detected_and_still_rolled_back(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    phone_.corrupt = True
    plan = new_plan(svc)
    ready(svc, plan)
    with pytest.raises(ValueError, match="mismatch"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    stored = svc.safety.load(plan["id"])
    assert stored["status"] == "interrupted" and stored["items"][0]["state"] == "hash-mismatch"
    result = svc.execute({"action": "safety-rollback", "plan": plan["id"], "confirm": True})
    assert result["removed"] == ["SymPort-TLS/MBedTLS.sis"] and not phone_.files


def test_plan_is_refused_for_another_phone_other_firmware_or_changed_files(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    plan = new_plan(svc)
    ready(svc, plan)
    phone_.row = phone(firmware="v 999.000")
    with pytest.raises(ValueError, match="firmware-changed"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    phone_.row = phone(model="Nokia E72")
    with pytest.raises(ValueError, match="model-or-rm-changed"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    phone_.row = phone()
    (tmp_path / "build/symport/revive/safety/artifacts" / svc.safety.load(plan["id"])["items"][0]["sha256"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact-missing"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert phone_.uploads == 0
    # rollback of an old plan is also refused on a different phone
    phone_.row = phone(model="Nokia E72")
    stored = svc.safety.load(plan["id"])
    stored["items"][0]["created"] = True
    svc.safety.save(stored)
    with pytest.raises(ValueError, match="another phone"):
        svc.execute({"action": "safety-rollback", "plan": plan["id"], "confirm": True})


def test_disconnected_phone_cannot_apply_and_reconnect_resumes(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    plan = new_plan(svc)
    ready(svc, plan)
    phone_.present = False
    with pytest.raises(ValueError, match="not connected"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    phone_.present = True
    assert svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})["status"] == "transferred-awaiting-manual-install"


def test_high_risk_component_needs_a_separate_acknowledgement(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("sys/bin/ssl.dll", b"synthetic")
    raw = buffer.getvalue()
    svc.tls.components["ssl-patch"] = dict(svc.tls.components["ssl-patch"], size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    svc.execute({"action": "tls-import", "name": "ssl.zip", "content": b64(raw)})
    plan = new_plan(svc, ("ssl-patch",))
    assert plan["risk"]["level"] == "high" and plan["risk"]["irreversible"] is True
    assert [i["name"] for i in plan["items"]] == ["MBedTLS.sis", "ssl.zip"]
    assert [b["code"] for b in plan["blocking"]] == ["manual-system-replacement"]
    ready(svc, plan)
    with pytest.raises(ValueError, match="Blocked: manual-system-replacement"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    with pytest.raises(ValueError, match="Unknown risk"):
        svc.execute({"action": "safety-ack", "plan": plan["id"], "codes": ["nope"], "confirm": True})
    after = svc.execute({"action": "safety-ack", "plan": plan["id"], "codes": ["manual-system-replacement"], "confirm": True})
    assert after["blocking"] == []
    assert svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})["status"] == "transferred-awaiting-manual-install"


def test_postflight_is_read_only_compares_and_never_claims_success(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    plan = new_plan(svc)
    ready(svc, plan)
    svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    calls_before = len(phone_.calls)
    ok = svc.execute({"action": "safety-postflight", "plan": plan["id"]})
    assert ok["identity"] == "unchanged" and ok["files"] == [{"path": "SymPort-TLS/MBedTLS.sis", "state": "present-hash-match"}]
    assert ok["installation"] == "unknown" and "nothing here proves" in ok["statement"]
    assert all(c[0] in ("download",) for c in phone_.calls[calls_before:])
    phone_.row = phone(firmware="v 2.0 after")
    changed = svc.execute({"action": "safety-postflight", "plan": plan["id"]})
    assert changed["identity"] == "changed" and {"field": "firmware", "before": "v 081.003.1.3", "after": "v 2.0 after"} in changed["diff"]
    del phone_.files["SymPort-TLS/MBedTLS.sis"]
    assert svc.execute({"action": "safety-postflight", "plan": plan["id"]})["files"][0]["state"] == "missing"


def test_checklist_is_manual_validated_and_exported_without_private_data(tmp_path):
    svc, phone_, _ = setup(tmp_path)
    plan = new_plan(svc)
    ready(svc, plan)
    svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    with pytest.raises(ValueError):
        svc.execute({"action": "safety-checklist", "plan": plan["id"], "item": "boot", "result": "pass"})
    with pytest.raises(ValueError):
        svc.execute({"action": "safety-checklist", "plan": plan["id"], "item": "imei", "result": "pass", "confirm": True})
    svc.execute({"action": "safety-checklist", "plan": plan["id"], "item": "wifi", "result": "fail", "confirm": True})
    report = json.loads(base64.b64decode(svc.execute({"action": "safety-export", "plan": plan["id"]})["content"]))
    assert report["checklist"]["wifi"] == {"result": "fail", "at": report["checklist"]["wifi"]["at"], "source": "manual"}
    assert report["physical_device_verification"] == "not-performed" and report["snapshot"]["complete_phone_backup"] is False
    assert set(report["device"]) == {"model", "rm", "firmware", "transport", "connection_kind", "fingerprint"}
    assert all(set(e) == {"at", "action", "status"} for e in report["events"])


def test_state_lists_plans_and_rejects_bad_ids_and_scenarios(tmp_path):
    svc, _, _ = setup(tmp_path)
    plan = new_plan(svc)
    state = svc.execute({"action": "safety-state", "device": "usb"})
    assert state["plans"][0]["id"] == plan["id"] and state["kinds"]["firmware"] == "not available"
    for bad in ("../../etc/passwd", "x" * 32, 5):
        with pytest.raises(ValueError):
            svc.execute({"action": "safety-export", "plan": bad})
    with pytest.raises(ValueError, match="Unknown scenario"):
        svc.execute({"action": "safety-plan", "scenario": "wipe", "device": "usb"})


@pytest.mark.parametrize("kw", [{"model": "N95-2", "rm": "RM-159"}, {"model": None, "firmware": None}, {"model": "Nokia E71"}])
def test_scenario_gate_blocks_unidentified_or_unsupported_phones(tmp_path, kw):
    svc, phone_, _ = setup(tmp_path)
    phone_.row = phone(**kw)
    plan = new_plan(svc)
    assert any(b["code"] == "gate-identity" for b in plan["blocking"])
    ready(svc, plan)
    with pytest.raises(ValueError, match="Blocked: gate-identity"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert phone_.uploads == 0


def test_removed_direct_transfer_cannot_bypass_the_safety_net(tmp_path):
    svc, _, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="Unknown Revive operation"):
        svc.execute({"action": "tls-transfer", "device": "usb", "component": "mbedtls-lib", "confirm": True})
