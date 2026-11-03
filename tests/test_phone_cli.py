import json
import os
import subprocess
import sys

from tests.helpers import REPO

FIX = REPO / "tests" / "fixtures"


def sp(*args):
    env = dict(os.environ, PYTHONPATH=str(REPO))
    r = subprocess.run([sys.executable, "-m", "symport", *args, "--json"], capture_output=True, text=True, cwd=REPO, env=env)
    return r.returncode, json.loads(r.stdout)


def card(tmp_path):
    c = tmp_path / "card"
    (c / "Images").mkdir(parents=True)
    (c / "Images" / "a.jpg").write_bytes(b"jpeg" * 1000)
    (c / "notes.txt").write_text("n")
    return c


def test_backup_cli_cycle(tmp_path):
    c = card(tmp_path)
    rc, d = sp("phone", "backup", "create", "--volume", str(c), "--dest", str(tmp_path / "bk"))
    assert rc == 0 and d["data"]["files"] == 2 and d["data"]["complete"] is True
    assert any("File backup only" in x for x in d["limitations"])
    assert d["verification"]["physical_device"] == "not-tested"
    rc, d = sp("phone", "backup", "verify", str(tmp_path / "bk"))
    assert rc == 0 and d["data"]["verify"]["ok"]
    new = tmp_path / "new"
    new.mkdir()
    rc, d = sp("phone", "backup", "restore", str(tmp_path / "bk"), "--volume", str(new))
    assert rc == 0 and d["data"]["restore"]["plan"]["new"] == 2 and not (new / "notes.txt").exists()
    rc, d = sp("phone", "backup", "restore", str(tmp_path / "bk"), "--volume", str(new), "--apply")
    assert rc == 0 and d["data"]["restore"]["verified"] == 2 and (new / "notes.txt").read_text() == "n"


def test_backup_cli_reports_failures(tmp_path):
    c = card(tmp_path)
    rc, d = sp("phone", "backup", "create", "--volume", str(c), "--dest", str(c / "inside"))
    assert rc == 1 and d["status"] == "failed"
    rc, d = sp("phone", "backup", "verify", str(tmp_path))
    assert rc == 1 and "not a SymPort backup" in d["checks"][0]["message"]
    (c / "bad").symlink_to(tmp_path)
    rc, d = sp("phone", "backup", "create", "--volume", str(c), "--dest", str(tmp_path / "bk2"))
    assert rc == 0 and any(x["id"] == "backup.skipped" for x in d["checks"])
    assert d["data"]["complete"] is False


def test_stage_cli(tmp_path):
    c = card(tmp_path)
    sis = FIX / "sdk_probe_package.sis"
    rc, d = sp("phone", "stage", str(sis), "--volume", str(c))
    assert rc == 0 and d["verification"]["physical_device"] == "staged-not-installed"
    assert any(x["id"] == "device.install" and x["status"] == "unknown" for x in d["checks"])
    assert (c / "Installs" / "sdk_probe_package.sis").is_file()
    rc, d = sp("phone", "stage", str(sis), "--volume", str(c))
    assert rc == 1 and "already exists" in d["checks"][-1]["message"]
    junk = tmp_path / "x.sis"
    junk.write_bytes(b"junk")
    rc, d = sp("phone", "stage", str(junk), "--volume", str(c))
    assert rc == 1 and not (c / "Installs" / "x.sis").exists()
    rc, d = sp("phone", "stage", str(sis), "--volume", str(c), "--folder", "../up")
    assert rc == 1 and not (tmp_path / "up").exists()
    rc, d = sp("phone", "stage", str(sis), "--volume", str(c), "--folder", "/abs")
    assert rc == 1


def test_apps_inventory_cli(tmp_path):
    c = card(tmp_path)
    (c / "p.sis").write_bytes((FIX / "sdk_probe_package.sis").read_bytes())
    rc, d = sp("phone", "apps", "inventory", "--volume", str(c))
    assert rc == 0 and d["data"]["inventory"]["packages"][0]["name"] == "Symbian E32 Probe"
    inst = next(x for x in d["checks"] if x["id"] == "inventory.installed_state")
    assert inst["status"] == "unknown" and inst["level"] == "device"
