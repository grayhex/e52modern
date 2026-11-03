"""Shared loopback API, outbound relay and Windows credential self-checks."""

import json
import threading
from http.client import HTTPConnection

import pytest

from symport.bridge.main import self_test
from symport.bridge.relay import validate_origin
from symport.bridge.server import BridgeServer
from symport.bridge.settings import load_key, protect
from symport.phone.relay import BrowserBridgeRelay


class Manager:
    def execute(self, data):
        return {"devices": [], "action": data["action"]}


@pytest.fixture
def bridge():
    server = BridgeServer(Manager(), "x" * 32, port=0, origins=["https://symport.example"])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(3)


def call(server, body, headers=None, path="/api/bridge"):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(
        "POST",
        path,
        json.dumps(body),
        {"Content-Type": "application/json", "X-Symport-Bridge-Key": "x" * 32, **(headers or {})},
    )
    r = connection.getresponse()
    result = r.status, json.loads(r.read())
    connection.close()
    return result


def test_auth_host_origin_and_dangerous_confirmation(bridge):
    assert call(bridge, {"action": "discover"})[0] == 200
    for headers in [
        {"Host": "attacker.invalid"},
        {"Origin": "https://attacker.invalid"},
        {"X-Symport-Bridge-Key": "wrong"},
    ]:
        assert call(bridge, {"action": "discover"}, headers)[0] == 403
    assert call(bridge, {"action": "delete", "confirm": True})[0] == 403
    bridge.approve = lambda data: True
    assert call(bridge, {"action": "delete", "confirm": True})[0] == 200
    assert call(bridge, {"action": "delete", "confirm": False})[0] == 400


def test_pair_requires_origin_and_local_approval(bridge):
    received = []
    bridge.pair = lambda origin, token: received.append((origin, token)) or True
    data = {"origin": "https://symport.example", "token": "y" * 32}
    assert call(bridge, data, path="/api/bridge/pair")[0] == 400
    assert (
        call(
            bridge,
            dict(data, origin="https://attacker.invalid"),
            {"Origin": data["origin"]},
            "/api/bridge/pair",
        )[0]
        == 400
    )
    assert call(bridge, data, {"Origin": data["origin"]}, "/api/bridge/pair")[0] == 200
    assert received == [(data["origin"], data["token"])]
    assert call(bridge, data, {"Origin": data["origin"]}, "/api/bridge/pair")[0] == 429


@pytest.mark.parametrize(
    "origin",
    [
        "http://remote.invalid",
        "https://user:pass@remote.invalid",
        "https://remote.invalid/path",
        "file:///tmp/x",
        "https://remote.invalid?x",
    ],
)
def test_origin_rejects_untrusted_url_forms(origin):
    with pytest.raises(ValueError):
        validate_origin(origin)


def test_dpapi_private_key(tmp_path):
    assert protect(protect(b"private-owner-value"), True) == b"private-owner-value"
    key = load_key(tmp_path)
    assert len(key) >= 32 and load_key(tmp_path) == key


def test_relay_only_issues_once_and_revokes():
    relay = BrowserBridgeRelay()
    assert relay.authorized(relay.token) and not relay.authorized("wrong")
    relay.last_seen = __import__("time").monotonic()
    output = []
    thread = threading.Thread(target=lambda: output.append(relay.execute({"action": "discover"})))
    thread.start()
    work = relay.poll()["request"]
    assert work["data"]["action"] == "discover"
    relay.complete({"id": work["id"], "result": {"devices": []}})
    thread.join(3)
    assert output == [{"devices": []}]
    with pytest.raises(ValueError):
        relay.complete({"id": work["id"], "result": {}})
    relay.close()
    assert not relay.authorized(relay.token)


def test_local_self_test(tmp_path, monkeypatch):
    for name in (
        "SYMPORT_BRIDGE_URL",
        "SYMPORT_GAMMU_CONFIG",
        "SYMPORT_CONNECTIONS_FILE",
        "SYMPORT_DEVICE_ROOTS",
        "SYMPORT_BRIDGE_DATA",
    ):
        monkeypatch.setenv(name, "")
    path = tmp_path / "report.json"
    self_test(path)
    result = json.loads(path.read_text())
    assert result["http_auth"] == "passed" and result["dns_rebinding"] == "passed"
    assert result["physical_device"] == "not-tested"
