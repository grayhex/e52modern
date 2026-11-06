"""Settings and databases backup (#36 addendum): capability-aware export, manifest, damaged archives, restore."""
import base64
import io
import json
import zipfile

import pytest

from symport.phone import DeviceManager
from symport.revive import ReviveService
from tests.capfake import row
from tests.test_revive import READS, WRITES, phone
from tests.test_safety import SafetyPhone

CONTACTS = [{"name": "Private Person", "numbers": ["+100000"]}]


class PimPhone(SafetyPhone):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.contacts = list(CONTACTS)
        self.conflicts = []
        self.apply_status = "verified-by-readback"
        self.calls_log = []

    def execute(self, data):
        a = data["action"]
        self.calls_log.append(a)
        if a == "personal-read":
            return {"snapshot": "s" * 32, "domain": data["domain"], "rows": self.contacts}
        if a == "personal-export":
            return {"content": base64.b64encode(json.dumps({"domain": "contacts", "rows": self.contacts}).encode()).decode(), "name": "x.json", "mime": "application/json"}
        if a == "personal-preview":
            return {"plan": "p" * 32, "dry_run": True, "changes": [{"operation": "add", "before": None, "after": r} for r in data["rows"]],
                    "conflicts": self.conflicts, "skipped": 0, "deletions": 0}
        if a == "personal-apply":
            return {"status": self.apply_status, "verified": 1, "requested": 1, "backup": "c" * 32}
        return super().execute(data)


def make(tmp_path, available=("contacts.read",), **kw):
    transport = PimPhone(**kw)
    transport.row = row({**transport.row}, available=(*READS, *available), untested_writes=WRITES)
    return ReviveService(tmp_path, DeviceManager(tmp_path, transport)), transport


def export(svc, cats=("contacts",)):
    return svc.execute({"action": "settings-export", "device": "usb", "categories": list(cats), "confirm": True, "owner_consent": True})


def levels(state):
    return {c["id"]: c["level"] for c in state["categories"]}


def test_levels_follow_verified_capabilities_and_never_overpromise(tmp_path):
    svc, _ = make(tmp_path)
    state = svc.execute({"action": "settings-state", "device": "usb"})
    lv = levels(state)
    assert lv["contacts"] == "exportable" and lv["calendar"] == "unverified" and lv["sms"] == "unverified"
    assert lv["notes"] == "unavailable" and lv["app-settings"] == "unavailable" and lv["system-databases"] == "unavailable"
    assert lv["profiles"] == "manual-only"
    assert state["levels"] == ["exported", "restored-with-readback", "manual-only", "unavailable"]
    assert "Not a backup of the phone" in state["statement"] and "promises nothing after a CFW" in state["statement"]


def test_unsupported_transport_marks_the_store_unavailable(tmp_path):
    svc, transport = make(tmp_path)
    transport.row = row({**phone()}, available=READS, unsupported=("contacts.read", "calendar.read"))
    lv = levels(svc.execute({"action": "settings-state", "device": "usb"}))
    assert lv["contacts"] == "unavailable" and lv["calendar"] == "unavailable"
    with pytest.raises(ValueError, match="not verified"):
        export(svc)


def test_export_needs_consent_and_a_verified_capability(tmp_path):
    svc, _ = make(tmp_path)
    for bad in ({"confirm": True}, {"owner_consent": True}, {}):
        with pytest.raises(ValueError, match="own this phone"):
            svc.execute({"action": "settings-export", "device": "usb", "categories": ["contacts"], **bad})
    with pytest.raises(ValueError, match="not verified"):
        export(svc, ("sms",))
    for bad in ([], ["contacts", "contacts"], ["notes"], ["contacts", "calendar", "tasks", "sms", "x"]):
        with pytest.raises(ValueError):
            svc.execute({"action": "settings-export", "device": "usb", "categories": bad, "confirm": True, "owner_consent": True})


def test_manifest_is_versioned_hashed_and_free_of_private_data(tmp_path):
    svc, _ = make(tmp_path)
    result = export(svc)
    manifest = result["manifest"]
    assert manifest["schema"] == "symport.settings-backup/1" and manifest["secrets"] == "none-collected"
    entry = manifest["categories"]["contacts"]
    assert entry["status"] == "exported" and entry["count"] == 1 and len(entry["sha256"]) == 64
    assert "not verified complete" in entry["completeness"] and entry["import_schema"] == "symport.personal.contacts/1"
    assert {"model", "rm", "firmware", "fingerprint"} <= set(manifest["device"])
    assert "Private Person" not in json.dumps(manifest) and "+100000" not in json.dumps(manifest)
    payload = tmp_path / "build/symport/revive/settings-backups" / result["backup"] / "payload/contacts.json"
    assert "Private Person" in payload.read_text() and oct(payload.stat().st_mode & 0o777) == "0o600"
    log = (tmp_path / "build/symport/device-manager/operations.jsonl").read_text()
    assert "Private Person" not in log
    state = svc.execute({"action": "settings-state", "device": "usb"})
    assert "Private Person" not in json.dumps(state)


def test_archive_roundtrip_and_damaged_archives_are_refused(tmp_path):
    svc, _ = make(tmp_path)
    backup = export(svc)["backup"]
    archive = svc.execute({"action": "settings-download", "backup": backup})
    assert archive["contains_private_data"] is True and "private data" in archive["warning"]
    svc.execute({"action": "settings-delete", "backup": backup, "confirm": True})
    with pytest.raises(ValueError, match="Unknown backup"):
        svc.execute({"action": "settings-download", "backup": backup})
    assert svc.execute({"action": "settings-import", "content": archive["content"]})["categories"] == ["contacts"]

    def mutate(fn):
        src = zipfile.ZipFile(io.BytesIO(base64.b64decode(archive["content"])))
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            fn(src, z)
        return base64.b64encode(out.getvalue()).decode()

    svc.execute({"action": "settings-delete", "backup": backup, "confirm": True})
    tampered = mutate(lambda s, z: [z.writestr(n, b'{"rows": []}' if n.endswith("contacts.json") else s.read(n)) for n in s.namelist()])
    with pytest.raises(ValueError, match="hash differs"):
        svc.execute({"action": "settings-import", "content": tampered})
    no_payload = mutate(lambda s, z: z.writestr("manifest.json", s.read("manifest.json")))
    with pytest.raises(ValueError, match="payload for contacts is missing"):
        svc.execute({"action": "settings-import", "content": no_payload})
    old = json.loads(zipfile.ZipFile(io.BytesIO(base64.b64decode(archive["content"]))).read("manifest.json"))
    old["schema"] = "symport.settings-backup/99"
    bad_schema = mutate(lambda s, z: z.writestr("manifest.json", json.dumps(old)))
    with pytest.raises(ValueError, match="Unsupported backup schema"):
        svc.execute({"action": "settings-import", "content": bad_schema})
    unsafe = mutate(lambda s, z: z.writestr("../manifest.json", b"{}"))
    with pytest.raises(ValueError, match="unsafe"):
        svc.execute({"action": "settings-import", "content": unsafe})
    for junk in ("", "***", base64.b64encode(b"not a zip").decode()):
        with pytest.raises(ValueError, match="Damaged archive"):
            svc.execute({"action": "settings-import", "content": junk})
    system = json.loads(zipfile.ZipFile(io.BytesIO(base64.b64decode(archive["content"]))).read("manifest.json"))
    system["categories"]["system-databases"] = system["categories"]["contacts"]
    with pytest.raises(ValueError, match="Unsupported category"):
        svc.execute({"action": "settings-import", "content": mutate(lambda s, z: [z.writestr("manifest.json", json.dumps(system)), z.writestr("payload/contacts.json", s.read("payload/contacts.json"))])})


def test_a_modified_stored_payload_is_never_restored(tmp_path):
    svc, _ = make(tmp_path)
    backup = export(svc)["backup"]
    (tmp_path / "build/symport/revive/settings-backups" / backup / "payload/contacts.json").write_text('{"rows": [{"name": "Injected"}]}')
    with pytest.raises(ValueError, match="damaged"):
        svc.execute({"action": "settings-restore-preview", "device": "usb", "backup": backup, "category": "contacts"})


def test_restore_previews_conflicts_then_writes_one_store_with_readback(tmp_path):
    svc, transport = make(tmp_path)
    backup = export(svc)["backup"]
    preview = svc.execute({"action": "settings-restore-preview", "device": "usb", "backup": backup, "category": "contacts"})
    assert preview["dry_run"] is True and preview["blocked"] is False and preview["changes"][0]["operation"] == "add"
    assert "personal-apply" not in transport.calls_log
    with pytest.raises(ValueError, match="Confirm"):
        svc.execute({"action": "settings-restore-apply", "device": "usb", "backup": backup, "category": "contacts", "snapshot": preview["snapshot"], "plan": preview["plan"]})
    done = svc.execute({"action": "settings-restore-apply", "device": "usb", "backup": backup, "category": "contacts",
                        "snapshot": preview["snapshot"], "plan": preview["plan"], "confirm": True})
    assert done["level"] == "restored-with-readback" and done["checkpoint"] == "c" * 32
    transport.apply_status = "partial-or-unverified"
    unverified = svc.execute({"action": "settings-restore-apply", "device": "usb", "backup": backup, "category": "contacts",
                              "snapshot": preview["snapshot"], "plan": preview["plan"], "confirm": True})
    assert unverified["level"] == "unverified" and "could not be verified" in unverified["statement"]


def test_conflicts_and_another_phone_block_the_restore(tmp_path):
    svc, transport = make(tmp_path)
    backup = export(svc)["backup"]
    transport.conflicts = [{"row": 0, "reason": "ambiguous match"}]
    assert svc.execute({"action": "settings-restore-preview", "device": "usb", "backup": backup, "category": "contacts"})["blocking"] == ["conflicts"]
    transport.conflicts = []
    transport.row = row({**phone(model="Nokia E72")}, available=(*READS, "contacts.read"), untested_writes=WRITES)
    other = svc.execute({"action": "settings-restore-preview", "device": "usb", "backup": backup, "category": "contacts"})
    assert other["other_phone"] is True and other["blocking"] == ["other-phone"]
    body = {"action": "settings-restore-apply", "device": "usb", "backup": backup, "category": "contacts", "snapshot": other["snapshot"], "plan": other["plan"], "confirm": True}
    with pytest.raises(ValueError, match="another phone"):
        svc.execute(body)
    assert svc.execute({**body, "acknowledge_other_phone": True})["level"] == "restored-with-readback"


def test_sms_and_unreadable_stores_cannot_be_restored(tmp_path):
    svc, _ = make(tmp_path, available=("contacts.read", "sms.read"))
    backup = export(svc, ("contacts", "sms"))["backup"]
    manifest = svc.execute({"action": "settings-download", "backup": backup})
    assert manifest["contains_private_data"] is True
    with pytest.raises(ValueError, match="manual-only"):
        svc.execute({"action": "settings-restore-preview", "device": "usb", "backup": backup, "category": "sms"})
    with pytest.raises(ValueError, match="Choose a category"):
        svc.execute({"action": "settings-restore-preview", "device": "usb", "backup": backup, "category": "system-databases"})
    with pytest.raises(ValueError, match="Unknown backup"):
        svc.execute({"action": "settings-download", "backup": "../../etc"})
