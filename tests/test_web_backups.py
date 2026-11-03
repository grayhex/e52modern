"""Workbench backup jobs, backup store and calendar/inventory API (no phone, temporary directories)."""
import json
import os
import time

import pytest

from symport.phone import archive
from symport.phone.backups import BackupStore, BackupStoreError
from symport.web import Workbench
from tests.helpers import repo_copy
from tests.test_web import _http, http_server  # noqa: F401


@pytest.fixture
def env(tmp_path, monkeypatch):
    card = tmp_path / "card"
    (card / "Images").mkdir(parents=True)
    (card / "Images" / "a.jpg").write_bytes(os.urandom(2000))
    (card / "notes.txt").write_text("hello")
    monkeypatch.setenv("SYMPORT_DEVICE_ROOTS", json.dumps({"e52-card": str(card)}))
    monkeypatch.delenv("SYMPORT_BRIDGE_URL", raising=False)
    monkeypatch.delenv("SYMPORT_GAMMU_CONFIG", raising=False)
    monkeypatch.delenv("SYMPORT_BACKUP_ROOT", raising=False)
    repo = repo_copy(tmp_path / "repo", with_src=False)
    return repo, card, Workbench(repo)


def wait(wb, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        snap = wb.snapshot()
        if snap["jobs"] and snap["jobs"][0]["status"] != "running":
            return snap["jobs"][0]
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_store_ids_and_listing(tmp_path):
    store = BackupStore(tmp_path / "b")
    for bad in ("../x", "a", "a/b", "", None, 5, "x" * 90, ".hidden", "a b"):
        with pytest.raises(BackupStoreError):
            store.path(bad)
    first = store.new_id("e52 card!")
    assert first.startswith("e52-card-")
    (store.root / first).mkdir(parents=True)
    assert store.new_id("e52 card!") != first                      # never reuses an existing id
    assert store.list()[0]["state"] == "incomplete"                # directory without manifest
    with pytest.raises(BackupStoreError):
        store.existing(first)


def test_create_verify_restore_through_jobs(env):
    repo, card, wb = env
    r = wb.launch({"action": "phone.backup.create", "device": "e52-card"})
    assert r["status"] == "running"
    job = wait(wb)
    assert job["status"] == "success" and "volume" not in job["command"] and str(card) not in job["command"]
    snap = wb.snapshot()
    assert len(snap["backups"]) == 1
    b = snap["backups"][0]
    assert b["files"] == 2 and b["complete"] and b["manifest_ok"] and b["label"] == "e52-card"
    assert snap["backup_free"] > 0
    assert not list((wb.backups.root / ".progress").glob("*.json")) if (wb.backups.root / ".progress").exists() else True

    wb.launch({"action": "phone.backup.verify", "id": b["id"]})
    assert wait(wb)["status"] == "success"

    target = repo.parent / "newcard"
    target.mkdir()
    (wb.devices.transport.files.roots)["e52-new"] = target
    wb.launch({"action": "phone.backup.restore", "id": b["id"], "device": "e52-new"})      # plan only
    plan = wait(wb)
    assert plan["status"] == "success" and not (target / "notes.txt").exists()
    assert plan["report"]["data"]["restore"]["plan"]["new"] == 2
    with pytest.raises(ValueError, match="Подтвердите"):
        wb.launch({"action": "phone.backup.restore", "id": b["id"], "device": "e52-new", "apply": True})
    wb.launch({"action": "phone.backup.restore", "id": b["id"], "device": "e52-new", "apply": True, "confirm": True})
    done = wait(wb)
    assert done["status"] == "success" and (target / "notes.txt").read_text() == "hello"
    assert done["report"]["data"]["restore"]["verified"] == 2


def test_inputs_are_validated_and_paths_never_come_from_the_browser(env):
    _repo, _card, wb = env
    for data, msg in [
        ({"action": "phone.backup.create", "device": "../etc"}, "накопитель"),
        ({"action": "phone.backup.create"}, "накопитель"),
        ({"action": "phone.backup.verify", "id": "../../etc"}, "идентификатор"),
        ({"action": "phone.backup.verify", "id": "valid-id-missing"}, "не найдена"),
        ({"action": "phone.backup.bogus"}, "Неизвестная"),
    ]:
        with pytest.raises(ValueError, match=msg):
            wb.launch(data)
    wb.launch({"action": "phone.backup.create", "device": "e52-card"})
    wait(wb)
    bid = wb.snapshot()["backups"][0]["id"]
    for only in ("../x", "/abs", "a/../b", "bad:name", "x" * 300):
        with pytest.raises(ValueError):
            wb.launch({"action": "phone.backup.restore", "id": bid, "device": "e52-card", "only": only})


def test_one_job_at_a_time_and_unavailable_without_local_volumes(env, tmp_path):
    _repo, _card, wb = env
    wb.jobs.append({"id": "x", "status": "running", "action": "doctor", "command": "", "started": "",
                    "finished": None, "exit_code": None, "report": None, "output": ""})
    with pytest.raises(RuntimeError):
        wb.launch({"action": "phone.backup.create", "device": "e52-card"})
    wb.jobs.clear()

    class Bridge:                                  # PC Bridge style transport has no local volumes
        def devices(self):
            return []

    wb.devices.transport = Bridge()
    with pytest.raises(ValueError, match="PC Bridge"):
        wb.launch({"action": "phone.backup.create", "device": "e52-card"})


def test_delete_requires_confirmation_and_stays_inside_the_store(env, tmp_path):
    _repo, card, wb = env
    wb.launch({"action": "phone.backup.create", "device": "e52-card"})
    wait(wb)
    bid = wb.snapshot()["backups"][0]["id"]
    with pytest.raises(BackupStoreError, match="Подтвердите"):
        wb.backups.delete(bid, None)
    outside = tmp_path / "outside-dir"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    os.symlink(outside, wb.backups.root / "evil-link-id")
    with pytest.raises(BackupStoreError):
        wb.backups.delete("evil-link-id", True)
    assert (outside / "keep.txt").exists()
    assert wb.backups.delete(bid, True) == {"deleted": bid}
    assert (card / "notes.txt").exists()                           # the phone volume is never touched
    assert all(b["id"] != bid for b in wb.snapshot()["backups"])


def test_http_delete_endpoint_security(env, tmp_path):
    import threading
    from http.server import ThreadingHTTPServer

    from symport.web import make_handler
    _repo, _card, wb = env
    wb.launch({"action": "phone.backup.create", "device": "e52-card"})
    wait(wb)
    bid = wb.snapshot()["backups"][0]["id"]
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(wb))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_port
    try:
        tok = {"X-Symport-Token": wb.token}
        assert _http(port, "POST", "/api/backups", {"action": "delete", "id": bid, "confirm": True})[0] == 403
        assert _http(port, "POST", "/api/backups", {"action": "delete", "id": bid}, tok)[0] == 400
        assert _http(port, "POST", "/api/backups", {"action": "delete", "id": "../x", "confirm": True}, tok)[0] == 400
        assert _http(port, "POST", "/api/backups", {"action": "rename", "id": bid}, tok)[0] == 400
        status, body = _http(port, "POST", "/api/backups", {"action": "delete", "id": bid, "confirm": True}, tok)
        assert status == 200 and json.loads(body) == {"deleted": bid}
        for asset in ("/compact.css", "/backups.js", "/calendar.js"):
            assert _http(port, "GET", asset)[0] == 200
    finally:
        server.shutdown()
        server.server_close()


def test_progress_file_is_counters_only(env):
    _repo, card, wb = env
    bid = "e52-card-test"
    path = wb.backups.progress_path(bid)
    from symport.phone.backups import write_progress
    write_progress(path, 3, 10, 300, 1000)
    assert wb.backups.progress(bid) == {"done": 3, "total": 10, "bytes": 300, "bytes_total": 1000}
    assert "jpg" not in path.read_text()


def test_archive_progress_callback_reports_counters(env, tmp_path):
    _repo, card, _wb = env
    seen = []
    archive.create(card, tmp_path / "bk", progress=lambda *a: seen.append(a))
    assert seen[-1][0] == seen[-1][1] == 2 and seen[-1][3] == seen[-1][4]
