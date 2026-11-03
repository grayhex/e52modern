"""Local workbench tests: safe command allow-list and real HTTP endpoints."""
from __future__ import annotations

import http.client
import json
import threading
import time
from http.server import ThreadingHTTPServer

import pytest

from symport.web import Workbench, command, make_handler, package_path, packages


@pytest.fixture
def repo(tmp_path):
    for variant in ("light", "dark"):
        (tmp_path / "build" / "symport" / "theme" / variant).mkdir(parents=True)
    (tmp_path / "workspace").mkdir()
    return tmp_path


def test_allowed_actions_and_untrusted_input(repo):
    assert command(repo, {"action": "theme.build", "variant": "light"}) == [
        "theme", "build", "--variant", "light", "--bootstrap"
    ]
    assert command(repo, {"action": "theme.package", "backend": "auto"})[-2:] == [
        "--backend", "auto"
    ]
    for data in (
        {"action": "shell", "cmd": "rm -rf /"},
        {"action": "theme.build", "variant": "../../tmp"},
        {"action": "theme.package", "backend": "bash"},
        {"action": "app.init", "project": "../outside"},
        {"action": "app.init", "project": "-injection"},
        {"action": "device.info", "selector": "device\nsecret"},
        {"action": "sis.inspect", "package": "/etc/passwd"},
    ):
        with pytest.raises(ValueError):
            command(repo, data)


def test_only_generated_packages_are_downloadable(repo):
    directory = repo / "build" / "symport" / "theme" / "light"
    (directory / "e52clearlight.sis").write_bytes(b"test")
    (directory / "private.txt").write_bytes(b"secret")
    items = packages(repo)
    assert len(items) == 1 and items[0]["name"] == "e52clearlight.sis"
    assert package_path(repo, items[0]["id"]).read_bytes() == b"test"
    with pytest.raises(ValueError):
        package_path(repo, "theme:light:../../private.txt")
    assert command(repo, {"action": "sis.inspect", "package": items[0]["id"]})[:2] == [
        "sis", "inspect"
    ]


def test_user_report_does_not_infer_device_success(repo):
    workbench = Workbench(repo)
    report = workbench.save_report({
        "rm": "RM-469", "firmware": "test", "notes": "manual entry",
        "steps": {"install": "pass", "activate": "fail"},
    })
    assert report["evidence"].startswith("manual")
    assert report["steps"]["activate"] == "fail"
    assert report["steps"]["identify"] == "pending"
    assert workbench.read_report()["rm"] == "RM-469"
    assert "physical_device" not in workbench.read_report()
    with pytest.raises(ValueError):
        workbench.save_report({"steps": {"shell": "pass"}})


@pytest.fixture
def http_server(repo):
    state = Workbench(repo)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _http(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    hdr = {"Host": f"127.0.0.1:{port}"}
    hdr.update(headers or {})
    if body is not None:
        body = json.dumps(body).encode()
        hdr["Content-Type"] = "application/json"
    conn.request(method, path, body=body, headers=hdr)
    response = conn.getresponse()
    result = response.status, response.read()
    conn.close()
    return result


def test_http_ui_and_security(http_server):
    state, port = http_server
    status, body = _http(port, "GET", "/")
    assert status == 200 and state.token.encode() in body and b"SymPort" in body
    status, body = _http(port, "GET", "/api/state")
    assert status == 200 and json.loads(body)["schema"] == "symport.web/1"
    status, _ = _http(port, "GET", "/api/state", headers={"Host": "evil.example"})
    assert status == 403
    status, _ = _http(port, "POST", "/api/device-report",
                      {"rm": "RM-469"}, {"X-Symport-Token": "invalid"})
    assert status == 403
    status, _ = _http(port, "POST", "/api/device-report", {"rm": "RM-469"},
                      {"X-Symport-Token": state.token, "Origin": "https://evil.test"})
    assert status == 403
    status, body = _http(port, "POST", "/api/device-report", {"rm": "RM-469"},
                         {"X-Symport-Token": state.token})
    assert status == 200 and json.loads(body)["rm"] == "RM-469"
    status, body = _http(port, "GET", "/api/device-report")
    assert status == 200 and json.loads(body)["rm"] == "RM-469"


def test_job_reports_real_cli_result(repo, monkeypatch):
    state = Workbench(repo)

    class Result:
        returncode = 3
        stderr = ""
        stdout = json.dumps({
            "schema": "symport.report/1", "status": "unsupported",
            "verification": {"physical_device": "not-tested"}})

    def fake_run(*args, **kwargs):
        assert kwargs["cwd"] == repo
        assert "-m" in args[0] and args[0][-1] == "--json"
        return Result()

    monkeypatch.setattr("symport.web.subprocess.run", fake_run)
    launched = state.launch({"action": "doctor"})
    assert launched["status"] == "running"
    for _ in range(100):
        if state.snapshot()["jobs"][0]["status"] != "running":
            break
        time.sleep(0.01)
    job = state.snapshot()["jobs"][0]
    assert job["status"] == "unsupported"
    assert job["report"]["verification"]["physical_device"] == "not-tested"
    assert (repo / "build" / "symport" / "web-reports" / (job["id"] + ".json")).is_file()
