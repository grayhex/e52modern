"""SymPort Revive (#33): readiness, plan statuses and honesty rules, without a physical phone."""
import json

import pytest

from symport.phone import DeviceManager
from symport.phone.files import MountedVolumes
from symport.revive import ReviveService
from tests.capfake import row

READS = ("identity.read", "storage.read", "files.list", "files.download")
WRITES = ("files.upload", "packages.transfer", "files.mkdir")


class Fake:
    def __init__(self, *rows):
        self.rows = list(rows)

    def devices(self):
        return [dict(r) for r in self.rows]

    def execute(self, data):
        raise AssertionError(f"Revive must not call the transport directly: {data}")


def phone(model="Nokia E52", rm=None, firmware="v 081.003.1.3", free=600 * 1024 * 1024, **extra):
    base = {"id": "usb", "transport": "windows-bridge", "connection_kind": "usb", "connected": True,
            "model": model, "rm": rm, "firmware": firmware, "free": free, "total": 2 * 1024**3,
            "storage_scope": "enrolled-filesystem", "capability_fingerprint_seed": 1}
    base.update(extra)
    return row(base, available=READS, untested_writes=WRITES)


def service(tmp_path, *rows):
    return ReviveService(tmp_path, DeviceManager(tmp_path, Fake(*rows)))


def checks(result):
    return {c["id"]: c for c in result["checks"]}


def test_e52_observed_identity_is_ready_and_facts_carry_their_source(tmp_path):
    result = service(tmp_path, phone()).execute({"action": "inspect", "device": "usb"})
    c = checks(result)
    assert c["identity"]["status"] == "ready" and c["identity"]["basis"] == "observed"
    assert c["platform"]["status"] == "ready" and "not a measured" in c["platform"]["reason"]["en"]
    assert result["facts"]["model"] == {"value": "Nokia E52", "source": "observed", "note": None}
    assert result["facts"]["platform"]["source"] == "documented"
    assert result["facts"]["rights"]["source"] == "unknown"
    assert result["facts"]["product_code"]["source"] == "unknown"
    assert "imei" not in json.dumps(result).lower()


def test_undefined_model_is_unknown_not_guessed(tmp_path):
    result = service(tmp_path, phone(model=None, firmware=None)).execute({"action": "inspect", "device": "usb"})
    c = checks(result)
    assert c["identity"]["status"] == "unknown"
    assert c["firmware"]["status"] == "unknown"
    assert result["facts"]["model"]["source"] == "unknown"


def test_manual_identity_is_separate_and_never_ready(tmp_path):
    mounted = row({"id": "usb", "transport": "mounted-volume", "connection_kind": "mass-storage",
                   "connected": True, "model": None, "rm": None, "firmware": None, "free": 10**9},
                  available=("files.list", "storage.read"))
    result = service(tmp_path, mounted).execute(
        {"action": "inspect", "device": "usb", "manual": {"model": "Nokia E52", "firmware": "v1"}})
    assert result["facts"]["model"]["source"] == "unknown"
    assert result["manual"]["model"] == "Nokia E52"
    c = checks(result)
    assert c["identity"]["status"] == "needs-action" and c["identity"]["basis"] == "manual"
    assert c["firmware"]["status"] == "needs-action"


def test_manual_input_cannot_override_the_device_report(tmp_path):
    result = service(tmp_path, phone()).execute(
        {"action": "inspect", "device": "usb", "manual": {"model": "Nokia N95", "rm": "RM-320"}})
    assert result["facts"]["model"]["value"] == "Nokia E52"
    assert result["conflict"] is not None
    assert checks(result)["identity"]["status"] == "needs-action"


@pytest.mark.parametrize("model,rm", [("N95-2", "RM-159"), ("N95", "RM-999"), ("Nokia N95", None)])
def test_n95_rm_mismatch_or_unknown_variant_needs_action(tmp_path, model, rm):
    result = service(tmp_path, phone(model=model, rm=rm)).execute(
        {"action": "plan", "device": "usb", "profile": "reborn-n95"})
    assert checks(result)["identity"]["status"] == "needs-action"
    assert result["status"] in ("needs-action", "unknown")
    assert all(o["status"] != "ready" for o in result["operations"] if o["id"] == "identify-device")


def test_rm_that_names_another_phone_is_a_mismatch(tmp_path):
    # Model alias says 8GB, RM says original: model and RM point to different phones.
    result = service(tmp_path, phone(model="N95 8GB", rm="RM-159")).execute({"action": "inspect", "device": "usb"})
    assert checks(result)["identity"]["status"] == "needs-action"


def test_reborn_profile_accepts_only_n95_family(tmp_path):
    e52 = service(tmp_path, phone()).execute({"action": "plan", "device": "usb", "profile": "reborn-n95"})
    assert checks(e52)["identity"]["status"] == "unsupported" and e52["status"] == "unsupported"
    n95 = service(tmp_path, phone(model="Nokia N95-1", rm="RM-159")).execute(
        {"action": "plan", "device": "usb", "profile": "reborn-n95"})
    assert checks(n95)["identity"]["status"] == "ready"
    assert checks(n95)["platform"]["status"] == "ready"
    # N95 8GB (RM-320) is a different phone: identified, but no automatic Reborn claim of support.
    eight = service(tmp_path, phone(model="N95 8GB", rm="RM-320")).execute(
        {"action": "plan", "device": "usb", "profile": "reborn-n95"})
    assert checks(eight)["identity"]["status"] == "ready"


def test_n97_mini_requires_explicit_variant_confirmation(tmp_path):
    svc = service(tmp_path, phone(model="Nokia N97 mini"))
    first = svc.execute({"action": "plan", "device": "usb", "profile": "app-kit"})
    assert checks(first)["identity"]["status"] == "needs-action"
    svc.execute({"action": "observe", "device": "usb", "kind": "variant", "confirmed": True,
                 "label": "RM-555", "confirm": True})
    second = svc.execute({"action": "plan", "device": "usb", "profile": "app-kit"})
    assert checks(second)["identity"]["status"] == "ready"


def test_unlisted_nokia_model_is_unsupported_not_ready(tmp_path):
    result = service(tmp_path, phone(model="Nokia E71")).execute({"action": "plan", "device": "usb", "profile": "app-kit"})
    assert checks(result)["identity"]["status"] == "unsupported"


def test_no_bridge_or_phone_gives_an_honest_empty_state(tmp_path):
    svc = service(tmp_path)
    inspect = svc.execute({"action": "inspect"})
    assert inspect["reason"] == "no-connection" and inspect["devices"] == []
    assert checks(inspect)["connection"]["status"] == "needs-action"
    plan = svc.execute({"action": "plan", "profile": "app-kit"})
    assert plan["reason"] == "no-connection" and plan["status"] in ("needs-action", "unknown")
    with pytest.raises(ValueError):
        svc.execute({"action": "record", "operation": "clock-check", "result": "done", "confirm": True})


def test_rights_only_on_memory_card_blocks_system_components(tmp_path):
    svc = service(tmp_path, phone(model="Nokia N95-1", rm="RM-159"))
    unknown = svc.execute({"action": "plan", "device": "usb", "profile": "reborn-n95"})
    assert checks(unknown)["rights"]["status"] == "unknown"
    with pytest.raises(ValueError):
        svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "memory-card"})
    svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "memory-card",
                 "patches": ["ROMPatcher+"], "confirm": True})
    card = svc.execute({"action": "plan", "device": "usb", "profile": "reborn-n95"})
    assert checks(card)["rights"]["status"] == "needs-action" and checks(card)["rights"]["basis"] == "manual"
    assert card["facts"]["rights"] == {"value": "memory-card", "source": "manual",
                                       "note": "Your observation; not readable through a file transport"}
    svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "device", "confirm": True})
    assert checks(svc.execute({"action": "plan", "device": "usb", "profile": "reborn-n95"}))["rights"]["status"] == "ready"


def test_observations_do_not_follow_a_different_phone(tmp_path):
    svc = service(tmp_path, phone(model="Nokia N95-1", rm="RM-159"))
    svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "device", "confirm": True})
    svc.devices.transport.rows = [phone(model="Nokia N95-1", rm="RM-159", firmware="other")]
    plan = svc.execute({"action": "plan", "device": "usb", "profile": "reborn-n95"})
    assert checks(plan)["rights"]["status"] == "unknown"


def test_unsupported_transport_blocks_transfer(tmp_path):
    obex = row({"id": "bt", "transport": "obex", "connection_kind": "bluetooth", "connected": True,
                "model": "Nokia E52", "firmware": "v1", "free": 10**9},
               available=("identity.read",), unsupported=("files.list", "files.download", "packages.transfer", "storage.read"))
    plan = service(tmp_path, obex).execute({"action": "plan", "device": "bt", "profile": "app-kit"})
    op = {o["id"]: o for o in plan["operations"]}["kit-transfer"]
    assert op["status"] == "unsupported" and "transfer" in op["blocking"]
    assert plan["status"] == "unsupported"


def test_low_space_and_unknown_space(tmp_path):
    low = service(tmp_path, phone(free=1024)).execute({"action": "plan", "device": "usb", "profile": "app-kit"})
    assert checks(low)["storage"]["status"] == "needs-action"
    unknown = service(tmp_path, phone(free=None)).execute({"action": "plan", "device": "usb", "profile": "app-kit"})
    assert checks(unknown)["storage"]["status"] == "unknown"


def test_operation_contract_and_no_install_claims(tmp_path):
    plan = service(tmp_path, phone()).execute({"action": "plan", "device": "usb", "profile": "app-kit"})
    assert plan["dry_run"] is True and "not installation" in plan["statement"]
    for op in plan["operations"]:
        assert {"risk", "prerequisites", "source", "version", "sha256", "restore_point", "execution", "result"} <= set(op)
        assert op["execution"] in ("read-only", "bridge-transfer", "manual-on-phone")
        assert op["result"]["result"] == "not-run"
    transfer = {o["id"]: o for o in plan["operations"]}["kit-transfer"]
    assert transfer["status"] == "ready" and transfer["risk"] == "medium"


def test_manual_results_are_recorded_as_manual_and_validated(tmp_path):
    svc = service(tmp_path, phone())
    with pytest.raises(ValueError):
        svc.execute({"action": "record", "device": "usb", "operation": "kit-install-manual", "result": "done"})
    with pytest.raises(ValueError):
        svc.execute({"action": "record", "device": "usb", "operation": "kit-transfer", "result": "done", "confirm": True})
    with pytest.raises(ValueError):
        svc.execute({"action": "record", "device": "usb", "operation": "kit-install-manual", "result": "installed", "confirm": True})
    svc.execute({"action": "record", "device": "usb", "operation": "kit-install-manual", "result": "done", "confirm": True})
    op = {o["id"]: o for o in svc.execute({"action": "plan", "device": "usb", "profile": "app-kit"})["operations"]}
    assert op["kit-install-manual"]["result"]["source"] == "manual"
    assert op["kit-transfer"]["result"]["result"] == "not-run"


def test_verify_compares_with_the_baseline_without_claiming_success(tmp_path):
    svc = service(tmp_path, phone())
    no_base = svc.execute({"action": "verify", "device": "usb"})
    assert no_base["baseline"] is None and checks(no_base)["baseline"]["status"] == "needs-action"
    svc.execute({"action": "baseline", "device": "usb"})
    svc.devices.transport.rows = [phone(free=500 * 1024 * 1024)]
    after = svc.execute({"action": "verify", "device": "usb"})
    assert {"field": "free", "before": 600 * 1024 * 1024, "after": 500 * 1024 * 1024, "delta": -100 * 1024 * 1024} in after["diff"]
    assert "do not prove" in after["statement"]
    assert checks(after)["baseline"]["status"] == "ready"


def test_unknown_actions_and_bad_input_are_rejected(tmp_path):
    svc = service(tmp_path, phone())
    for bad in ({"action": "install"}, {"action": "plan", "profile": "../x"}, {"action": 5}):
        with pytest.raises(ValueError):
            svc.execute(bad)
    huge = svc.execute({"action": "inspect", "device": "usb", "manual": {"model": "A" * 500, "rm": "\x00\x01"}})
    assert len(huge["manual"]["model"]) == 120 and "\x00" not in huge["manual"]["rm"]


def test_journal_holds_action_and_status_only(tmp_path):
    svc = service(tmp_path, phone())
    svc.execute({"action": "inspect", "device": "usb", "manual": {"model": "SECRET-MODEL"}})
    log = (tmp_path / "build/symport/device-manager/operations.jsonl").read_text()
    assert "revive-inspect" in log and "SECRET-MODEL" not in log


def test_mounted_volume_never_identifies_a_phone(tmp_path):
    root = tmp_path / "card"
    root.mkdir()
    devices = DeviceManager(tmp_path, MountedVolumes({"card": str(root)}))
    result = ReviveService(tmp_path, devices).execute({"action": "inspect", "device": "card"})
    assert checks(result)["identity"]["status"] == "unknown"
    assert result["facts"]["model"]["source"] == "unknown"
