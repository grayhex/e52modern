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


# ---- Symbian TLS / CA revival (#34) ---------------------------------------------------------------------
import base64  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import zipfile  # noqa: E402

from symport.revive.tls import STACKS, load_components  # noqa: E402

COMPONENTS = load_components()


def b64(raw):
    return base64.b64encode(raw).decode()


class MemoryPhone:
    """Identified phone with an in-memory filesystem; the only transport the TLS tests need."""

    def __init__(self, **kw):
        self.row = phone(**kw)
        self.files = {}
        self.calls = []

    def devices(self):
        return [dict(self.row)]

    def execute(self, data):
        self.calls.append(data["action"])
        path = data.get("path", "")
        if data["action"] == "mkdir":
            return {}
        if data["action"] == "upload":
            if path in self.files:
                raise FileExistsError(path)
            self.files[path] = base64.b64decode(data["content"])
            return {"status": "verified"}
        if data["action"] == "download":
            return {"content": b64(self.files[path])}
        raise AssertionError(data)


def tls_service(tmp_path, **kw):
    transport = MemoryPhone(**kw)
    svc = ReviveService(tmp_path, DeviceManager(tmp_path, transport))
    return svc, transport


def fake_artifact(key, raw):
    """Pretend the author's host serves ``raw`` (never touches the network)."""
    class Response:
        headers = {}

        def __init__(self):
            self.data = raw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def geturl(self):
            return COMPONENTS[key]["url"]

        def read(self, n=-1):
            return self.data[:n] if n >= 0 else self.data

    return type("Opener", (), {"open": lambda self, req, timeout=0: Response()})()


def test_pins_are_complete_licensed_and_never_bundled():
    assert set(COMPONENTS) == {"mbedtls-lib", "ssl-patch"}
    for c in COMPONENTS.values():
        assert len(c["sha256"]) == 64 and c["size"] > 0 and c["licence"]["spdx"] in ("Apache-2.0", "EPL-2.0")
        assert c["url"].startswith("https://nnproject.cc/") and c["observed_at"]
    assert COMPONENTS["ssl-patch"]["depends_on"] == ["mbedtls-lib"]
    from pathlib import Path

    assert not [p for p in (Path(__file__).resolve().parent.parent / "symport").rglob("*") if p.suffix in (".sis", ".zip", ".dll")]


def test_matrix_is_per_model_and_stack_with_honest_statuses(tmp_path):
    svc, _ = tls_service(tmp_path)
    state = svc.execute({"action": "tls-state", "device": "usb"})
    rows = {r["target"]: r for r in state["applicability"]}
    assert set(rows) == {"nokia-e52", "nokia-e72", "nokia-n95", "nokia-n95-8gb", "nokia-n97-mini"}
    assert rows["nokia-e52"]["symbian"] == "9.3" and rows["nokia-n95"]["symbian"] == "9.2" and rows["nokia-n97-mini"]["symbian"] == "9.4"
    for entry in rows.values():
        assert entry["stacks"]["system-ssl"]["status"] == "documented"
        assert entry["stacks"]["system-ssl"]["tested"] == "not-tested"
        assert entry["stacks"]["qt-ssl"]["status"] == "not-applicable"
        assert "not stated" in entry["stacks"]["system-ssl"]["patch_version"]
    assert set(STACKS) == {"system-ssl", "mbedtls-lib", "java-ssl", "qt-ssl"}
    assert all(c["device"]["state"] == "unknown" and not c["cached"] for c in state["components"])


def test_fetch_requires_exact_pin_and_refuses_changed_or_broken_files(tmp_path):
    svc, _ = tls_service(tmp_path)
    good = io.BytesIO()
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("sys/bin/ssl.dll", b"x" * 10)
    svc.tls.opener = fake_artifact("ssl-patch", good.getvalue())
    with pytest.raises(ValueError, match="hash-mismatch"):
        svc.execute({"action": "tls-fetch", "component": "ssl-patch"})
    assert not list((tmp_path / "build/symport/revive/tls").rglob("*.zip"))
    svc.tls.opener = fake_artifact("ssl-patch", b"not a zip at all")
    with pytest.raises(ValueError, match="hash-mismatch"):
        svc.execute({"action": "tls-fetch", "component": "ssl-patch"})


def test_offline_download_is_a_clear_failure_and_manual_import_remains(tmp_path):
    import urllib.error

    svc, _ = tls_service(tmp_path)

    class Offline:
        def open(self, *a, **k):
            raise urllib.error.URLError("no network")

    svc.tls.opener = Offline()
    with pytest.raises(ValueError, match="offline"):
        svc.execute({"action": "tls-fetch", "component": "mbedtls-lib"})
    with pytest.raises(ValueError, match="Unknown TLS component"):
        svc.execute({"action": "tls-fetch", "component": "../x"})


def pinned_zip(tmp_path, svc, monkeypatch):
    """Build a ZIP that *is* the pinned build by repinning the catalog to it (test-local)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("sys/bin/ssl.dll", b"synthetic ssl replacement")
    raw = buffer.getvalue()
    spec = dict(COMPONENTS["ssl-patch"], size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    svc.tls.components = dict(svc.tls.components, **{"ssl-patch": spec})
    return raw


def test_import_validates_structure_and_pin(tmp_path, monkeypatch):
    svc, _ = tls_service(tmp_path)
    raw = pinned_zip(tmp_path, svc, monkeypatch)
    result = svc.execute({"action": "tls-import", "name": "ssl.zip", "content": b64(raw)})
    assert result["component"] == "ssl-patch" and result["validation"]["contents"] == ["sys/bin/ssl.dll"]
    with pytest.raises(ValueError, match="hash-mismatch.*ssl-patch"):
        svc.execute({"action": "tls-import", "name": "ssl.zip", "content": b64(raw + b"x")})
    with pytest.raises(ValueError, match="broken-package"):
        svc.execute({"action": "tls-import", "name": "x.sis", "content": "!!!"})
    with pytest.raises(ValueError, match="hash-mismatch"):
        svc.execute({"action": "tls-import", "name": "unrelated.sis", "content": b64(b"\x00" * 64)})


def test_zip_with_key_material_or_extra_files_is_rejected(tmp_path):
    from symport.revive.tls import validate_component

    for extra in ("sys/bin/other.dll", "private.key"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("sys/bin/ssl.dll", b"a")
            z.writestr(extra, b"b")
        raw = buffer.getvalue()
        spec = dict(COMPONENTS["ssl-patch"], size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        with pytest.raises(ValueError, match="broken-package"):
            validate_component(spec, raw)


def obtained(tmp_path, svc, monkeypatch):
    raw = pinned_zip(tmp_path, svc, monkeypatch)
    svc.execute({"action": "tls-import", "name": "ssl.zip", "content": b64(raw)})
    return raw


def test_transfer_is_verified_by_readback_and_never_called_installed(tmp_path, monkeypatch):
    svc, phone_ = tls_service(tmp_path)
    raw = obtained(tmp_path, svc, monkeypatch)
    with pytest.raises(ValueError, match="Confirm"):
        svc.execute({"action": "tls-transfer", "device": "usb", "component": "ssl-patch"})
    result = svc.execute({"action": "tls-transfer", "device": "usb", "component": "ssl-patch", "confirm": True})
    assert result["state"] == "transferred-awaiting-install" and "not installed" in result["statement"]
    assert phone_.files["SymPort-TLS/ssl.zip"] == raw
    state = svc.execute({"action": "tls-state", "device": "usb"})
    assert {c["id"]: c["device"]["state"] for c in state["components"]}["ssl-patch"] == "transferred-awaiting-install"
    # A second transfer of the same bytes is idempotent; a different file is never overwritten.
    svc.execute({"action": "tls-transfer", "device": "usb", "component": "ssl-patch", "confirm": True})
    phone_.files["SymPort-TLS/ssl.zip"] = b"someone else's file"
    with pytest.raises(ValueError, match="conflict"):
        svc.execute({"action": "tls-transfer", "device": "usb", "component": "ssl-patch", "confirm": True})
    assert phone_.files["SymPort-TLS/ssl.zip"] == b"someone else's file"


def test_transfer_blocked_for_wrong_rm_unknown_model_and_missing_file(tmp_path, monkeypatch):
    for kw in ({"model": "N95-2", "rm": "RM-159"}, {"model": None, "firmware": None}, {"model": "Nokia E71"}):
        svc, phone_ = tls_service(tmp_path / (kw.get("model") or "none").replace(" ", "_"), **kw)
        obtained(tmp_path, svc, monkeypatch)
        with pytest.raises(ValueError, match="blocked"):
            svc.execute({"action": "tls-transfer", "device": "usb", "component": "ssl-patch", "confirm": True})
        assert "upload" not in phone_.calls
    svc, phone_ = tls_service(tmp_path / "nofile")
    with pytest.raises(ValueError, match="Obtain"):
        svc.execute({"action": "tls-transfer", "device": "usb", "component": "ssl-patch", "confirm": True})


def test_kit_orders_dependencies_and_gates_the_system_replacement(tmp_path, monkeypatch):
    svc, _ = tls_service(tmp_path)
    kit = svc.execute({"action": "tls-kit", "device": "usb", "components": ["ssl-patch"], "app_kind": "native-system"})
    assert [s["id"] for s in kit["steps"]] == ["mbedtls-lib", "ssl-patch"]
    patch = kit["steps"][1]
    assert patch["install"]["execution"] == "manual-on-phone" and patch["high_risk"]["privileged_adapter"] == "not-available"
    assert patch["high_risk"]["status"] == "needs-action" and len(patch["high_risk"]["requirements"]) == 2
    assert kit["stack_support"]["status"] == "documented" and kit["stack_support"]["tested"] == "not-tested"
    assert "high_risk" not in kit["steps"][0]
    svc.execute({"action": "observe", "device": "usb", "kind": "rights", "scope": "device", "confirm": True})
    svc.execute({"action": "tls-record", "device": "usb", "item": "ssl-original-backup", "state": "installed", "confirm": True})
    ready = svc.execute({"action": "tls-kit", "device": "usb", "components": ["ssl-patch"]})
    assert ready["steps"][1]["high_risk"]["status"] == "ready"
    # Even when every gate is green SymPort offers no automated system write.
    assert ready["steps"][1]["high_risk"]["privileged_adapter"] == "not-available"
    qt = svc.execute({"action": "tls-kit", "device": "usb", "components": ["mbedtls-lib"], "app_kind": "qt"})
    assert qt["stack_support"]["status"] == "not-applicable"
    java = svc.execute({"action": "tls-kit", "device": "usb", "components": ["mbedtls-lib"], "app_kind": "java"})
    assert java["stack_support"]["covered_by"] == "system-ssl"


def test_installed_is_only_what_the_user_reports(tmp_path):
    svc, _ = tls_service(tmp_path)
    with pytest.raises(ValueError):
        svc.execute({"action": "tls-record", "device": "usb", "item": "mbedtls-lib", "state": "installed"})
    with pytest.raises(ValueError):
        svc.execute({"action": "tls-record", "device": "usb", "item": "mbedtls-lib", "state": "fixed", "confirm": True})
    svc.execute({"action": "tls-record", "device": "usb", "item": "mbedtls-lib", "state": "installed", "confirm": True})
    svc.execute({"action": "tls-record", "device": "usb", "item": "https-test", "state": "fail", "host": "example.com", "confirm": True})
    state = svc.execute({"action": "tls-state", "device": "usb"})
    assert {c["id"]: c["device"] for c in state["components"]}["mbedtls-lib"]["state"] == "installed-reported"
    assert state["https"]["state"] == "fail" and state["https"]["source"] == "manual"


def test_diagnostics_say_where_they_ran_and_use_the_manual_clock(tmp_path):
    svc, _ = tls_service(tmp_path)
    svc.tls.probe = lambda host: {"ok": True, "tls_version": "TLSv1.3", "cipher": "X",
                                  "leaf": {"subject": "CN=" + host, "issuer": "CN=CA", "not_before": "Jan  1 00:00:00 2026 GMT",
                                           "not_after": "Jan  1 00:00:00 2027 GMT"}}
    ok = svc.execute({"action": "tls-diagnose", "host": "example.com", "phone_date": "2026-11-05"})
    assert ok["server_probe"]["ran_on"] == "server" and ok["bridge_probe"]["status"] == "not-available"
    assert ok["phone_test"]["ran_on"] == "phone" and ok["chain"]["status"] == "leaf-only"
    assert ok["clock"]["source"] == "manual"
    old = svc.execute({"action": "tls-diagnose", "host": "example.com", "phone_date": "2010-01-01"})
    assert old["clock"]["verdict"] == "needs-action" and old["clock"]["certificate_window"] == "phone-date-outside"
    with pytest.raises(ValueError):
        svc.execute({"action": "tls-diagnose", "host": "localhost"})
    with pytest.raises(ValueError):
        svc.execute({"action": "tls-diagnose", "host": "example.com", "phone_date": "yesterday"})


def test_probe_without_network_reports_offline_not_a_fake_success(tmp_path, monkeypatch):
    import socket as _socket

    from symport.revive import tls as T

    def boom(*a, **k):
        raise _socket.gaierror("no dns")

    monkeypatch.setattr(T.socket, "getaddrinfo", boom)
    assert T.default_probe("example.com") == {"ok": False, "error": "dns"}
    monkeypatch.setattr(T.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("127.0.0.1", 443))])
    assert T.default_probe("example.com")["error"] == "non-public-address"
