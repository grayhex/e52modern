"""Device Agent host (#38): pairing, per-operation permissions, honest levels. Mock agent only; no hardware."""
import base64

import pytest

from symport.agent import AgentHost, MockAgent
from symport.agent import protocol as P
from symport.phone import DeviceManager
from symport.revive import ReviveService
from tests.test_revive import Fake


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def paired(consent="granted", tamper=False, journal=None):
    clock = Clock()
    mock_holder = {}
    host = AgentHost(None, journal=journal, clock=clock)

    class Wire:
        def send(self, message):
            return mock_holder["agent"].send(message)

    host.transport = Wire()
    code = host.pair_start()["code"]
    mock_holder["agent"] = MockAgent(code, consent=consent, tamper=tamper)
    host.pair_finish()
    return host, mock_holder["agent"], clock


def payload(text=b"echo"):
    return {"path": "SymPort-Agent/echo.txt", "content": base64.b64encode(text).decode()}


def test_without_a_transport_the_agent_is_not_installed_and_nothing_works():
    host = AgentHost()
    state = host.state()
    assert state["status"] == "not-installed" and state["agent_binary"] == "not-built-in-this-change"
    assert "No generic system write" in state["statement"]
    with pytest.raises(ValueError, match="not installed"):
        host.pair_start()
    with pytest.raises(ValueError, match="not paired"):
        host.call("ping")
    with pytest.raises(ValueError, match="Pair"):
        host.grant("diagnostics.read")


def test_pairing_requires_the_code_and_expires():
    clock = Clock()
    host = AgentHost(None, clock=clock)
    holder = {}
    host.transport = type("W", (), {"send": lambda self, m: holder["a"].send(m)})()
    code = host.pair_start()["code"]
    holder["a"] = MockAgent("000000" if code != "000000" else "111111")
    with pytest.raises(ValueError, match="did not prove"):
        host.pair_finish()
    assert host.state()["status"] == "not-paired"
    host.pair_start()
    clock.t += P.PAIRING_TTL + 1
    with pytest.raises(ValueError, match="expired"):
        host.pair_finish()


def test_pairing_succeeds_and_levels_start_at_connected_only():
    host, _, _ = paired()
    state = host.state()
    assert state["status"] == "paired" and state["agent"]["synthetic"] is True and state["levels"] == ["agent-connected", "operation-completed", "device-verified"]
    assert all(v == 0 for v in state["permissions"].values())
    ping_blocked = host.call("ping")
    assert ping_blocked["levels"] == {"agent-connected": True, "operation-completed": True, "device-verified": False}
    assert ping_blocked["verification"] == "not-applicable"


def test_each_operation_needs_its_own_unexpired_permission():
    host, agent, clock = paired()
    with pytest.raises(ValueError, match="diagnostics.read is not granted"):
        host.call("sys.memory")
    host.grant("diagnostics.read", 120)
    assert host.call("sys.battery")["data"] == {"percent": 80, "charging": False}
    with pytest.raises(ValueError, match="patches.read"):
        host.call("sys.patches")
    clock.t += 121
    with pytest.raises(ValueError, match="not granted \\(or expired\\)"):
        host.call("sys.memory")
    host.grant("diagnostics.read")
    host.revoke("diagnostics.read")
    with pytest.raises(ValueError, match="not granted"):
        host.call("sys.memory")
    with pytest.raises(ValueError, match="not granted"):
        host.revoke("diagnostics.read")
    host.grant("patches.read")
    host.revoke()
    assert all(v == 0 for v in host.state()["permissions"].values())
    assert agent.seen.count("sys.memory") == 0


def test_read_replies_are_minimised_and_marked_synthetic():
    host, _, _ = paired()
    host.grant("diagnostics.read")
    host.grant("patches.read")
    mem = host.call("sys.memory")
    assert set(mem["data"]) == {"ram_free", "ram_total", "rom_free"} and mem["synthetic"] is True  # the IMEI the mock volunteered is dropped
    patches = host.call("sys.patches")
    assert patches["data"] == {"patches": [{"name": "Synthetic patch", "state": "applied"}]} and "secret_token" not in str(patches)


def test_forbidden_and_unknown_operations_are_refused_before_anything_is_sent():
    host, agent, _ = paired()
    for op in ("shell", "exec", "system.write", "jailbreak", "flash", "patch.apply", "file.delete-system", "shell.run", "x.y"):
        with pytest.raises(ValueError, match="forbidden by design|Unknown agent operation"):
            host.call(op)
    assert agent.seen == ["hello"]


def test_confirmed_actions_need_host_confirmation_and_visible_consent_on_the_phone():
    host, agent, _ = paired()
    host.grant("files.test")
    with pytest.raises(ValueError, match="Confirm this action"):
        host.call("file.echo-test", payload())
    done = host.call("file.echo-test", payload(), confirm=True)
    assert done["status"] == "completed" and done["levels"] == {"agent-connected": True, "operation-completed": True, "device-verified": True}
    assert agent.files["SymPort-Agent/echo.txt"] == b"echo"
    declined_host, declined_agent, _ = paired(consent="declined")
    declined_host.grant("files.test")
    result = declined_host.call("file.echo-test", payload(), confirm=True)
    assert result["status"] == "declined-on-phone" and result["levels"]["operation-completed"] is False and "SymPort-Agent/echo.txt" not in declined_agent.files


def test_a_wrong_read_back_hash_never_reaches_the_device_verified_level():
    host, _, _ = paired(tamper=True)
    host.grant("files.test")
    result = host.call("file.echo-test", payload(), confirm=True)
    assert result["levels"]["operation-completed"] is True and result["levels"]["device-verified"] is False and result["verification"] is False


def test_agent_writes_stay_inside_symport_folders_and_small():
    host, _, _ = paired()
    host.grant("files.send")
    host.grant("installer.open")
    for bad in ("../x", "C:/sys/bin/x.dll", "SymPort-Agent/sub/x", "Other/x.txt", "SymPort-Agent/", "SymPort-Agent/..\\x"):
        with pytest.raises(ValueError, match="SymPort-\\* folder"):
            host.call("file.send", {"path": bad, "content": "eA=="}, confirm=True)
        with pytest.raises(ValueError, match="SymPort-\\* folder"):
            host.call("install.open", {"path": bad}, confirm=True)
    with pytest.raises(ValueError, match="at most 64 KiB"):
        host.call("file.send", {"path": "SymPort-Agent/big.bin", "content": base64.b64encode(b"x" * 70000).decode()}, confirm=True)
    with pytest.raises(ValueError, match="Invalid content"):
        host.call("file.send", {"path": "SymPort-Agent/a.bin", "content": "***"}, confirm=True)
    opened = host.call("install.open", {"path": "SymPort-Agent/a.sis"}, confirm=True)
    assert opened["levels"]["device-verified"] is False and opened["verification"] == "not-applicable"  # opening an installer proves no installation


def test_contact_export_is_consented_minimised_and_hash_verified():
    host, _, _ = paired()
    host.grant("export.contacts")
    ok = host.call("export.contacts", {"fields": ["name"]})
    assert ok["levels"]["device-verified"] is True
    with pytest.raises(ValueError, match="name, numbers or emails"):
        host.call("export.contacts", {"fields": ["name", "ssn"]})
    bad_host, _, _ = paired(tamper=True)
    bad_host.grant("export.contacts")
    assert bad_host.call("export.contacts")["levels"]["device-verified"] is False
    refused_host, _, _ = paired(consent="declined")
    refused_host.grant("export.contacts")
    assert refused_host.call("export.contacts")["status"] == "declined-on-phone"


def test_tampered_or_replayed_replies_are_rejected():
    host, agent, _ = paired()
    inner = host.transport.send

    def tamper(message):
        reply = inner(message)
        reply["data"] = {"pong": False}
        return reply

    host.transport.send = tamper
    with pytest.raises(ValueError, match="failed authentication"):
        host.call("ping")
    host.transport.send = inner
    last = {}

    def replay(message):
        if "reply" in last:
            return last["reply"]
        last["reply"] = inner(message)
        return last["reply"]

    host.transport.send = replay
    host.call("ping")
    with pytest.raises(ValueError, match="does not match"):
        host.call("ping")


def test_disconnect_forgets_the_pairing_and_every_permission():
    host, _, _ = paired()
    host.grant("diagnostics.read")
    host.disconnect()
    assert host.state()["status"] == "not-paired" and host.state()["agent"] is None
    with pytest.raises(ValueError, match="not paired"):
        host.call("sys.memory")


def test_the_journal_records_actions_and_statuses_only():
    events = []
    host, _, _ = paired(journal=lambda a, s: events.append((a, s)))
    host.grant("files.send")
    host.call("file.send", payload(b"private bytes"), confirm=True)
    flat = str(events)
    assert ("agent-file.send", "success") in events and "private bytes" not in flat and "echo.txt" not in flat


def test_revive_exposes_the_agent_honestly_without_a_transport(tmp_path):
    svc = ReviveService(tmp_path, DeviceManager(tmp_path, Fake()))
    state = svc.execute({"action": "agent-state"})
    assert state["status"] == "not-installed" and "forbidden" in state and "shell" in state["forbidden"]
    for action in ("agent-pair-start", "agent-pair-finish", "agent-grant"):
        with pytest.raises(ValueError):
            svc.execute({"action": action, "permission": "diagnostics.read"})
    with pytest.raises(ValueError, match="forbidden by design"):
        svc.execute({"action": "agent-call", "op": "shell"})
    log = (tmp_path / "build/symport/device-manager/operations.jsonl").read_text()
    assert "revive-agent-state" in log
