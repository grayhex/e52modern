import json
import os
import subprocess
import sys

import pytest

from symport.phone import gammu_calendar, inventory
from symport.sis import writer
from tests.helpers import REPO, make_e32, write_tool

FIX = REPO / "tests" / "fixtures"

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Gammu test//EN
BEGIN:VEVENT
UID:1
DTSTART:20261105T090000
DTEND:20261105T100000
SUMMARY:Dentist
LOCATION:Clinic
RRULE:FREQ=YEARLY
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART;VALUE=DATE:20261201
SUMMARY:Birthday
END:VEVENT
BEGIN:VTODO
UID:3
SUMMARY:Buy batteries
DUE:20261106T180000
STATUS:NEEDS-ACTION
PRIORITY:1
END:VTODO
END:VCALENDAR
"""


def test_inventory_lists_valid_packages_and_reports_garbage(tmp_path):
    (tmp_path / "Installs").mkdir()
    (tmp_path / "Installs" / "a.sis").write_bytes((FIX / "sdk_probe_package.sis").read_bytes())
    (tmp_path / "Installs" / "b.sisx").write_bytes((FIX / "sdk_probe_package_signed.sis").read_bytes())
    (tmp_path / "Installs" / "bad.sis").write_bytes(b"not a package")
    (tmp_path / "Installs" / "readme.txt").write_text("ignored")
    inv = inventory.scan(tmp_path)
    names = {p["path"]: p for p in inv["packages"]}
    assert set(names) == {"Installs/a.sis", "Installs/b.sisx"}
    assert names["Installs/a.sis"]["signed"] is False and names["Installs/b.sisx"]["signed"] is True
    assert names["Installs/a.sis"]["uid"] == "0xe0000809" and names["Installs/a.sis"]["checksums_ok"]
    assert [u["path"] for u in inv["unreadable"]] == ["Installs/bad.sis"]
    assert list(inv["duplicates_by_uid"].values()) == [["Installs/a.sis", "Installs/b.sisx"]]
    assert "installed state" in inv["note"]


def test_inventory_does_not_follow_symlinked_directories(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.sis").write_bytes((FIX / "sdk_probe_package.sis").read_bytes())
    vol = tmp_path / "vol"
    vol.mkdir()
    os.symlink(outside, vol / "link")
    assert inventory.scan(vol)["packages"] == []


def test_inventory_flags_corrupt_checksums(tmp_path):
    raw = bytearray(writer.build(writer.SisPackage(0xE0000001, "T", "v", (1, 0, 0),
                                                   [writer.SisFile("!:\\sys\\bin\\t.exe", make_e32())])))
    raw[-5] ^= 0xFF
    (tmp_path / "t.sis").write_bytes(bytes(raw))
    assert inventory.scan(tmp_path)["packages"][0]["checksums_ok"] is False


def test_parse_ics_events_and_todos():
    d = gammu_calendar.parse_ics(ICS)
    assert [e["summary"] for e in d["events"]] == ["Dentist", "Birthday"]
    assert d["events"][0]["start"].startswith("2026-11-05T09:00") and d["events"][0]["recurrence"] == "FREQ=YEARLY"
    assert d["events"][1]["start"] == "2026-12-01"
    assert d["todos"][0]["summary"] == "Buy batteries" and d["todos"][0]["status"] == "NEEDS-ACTION"


@pytest.mark.parametrize("raw", [b"BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY", b"\x00\x01\x02garbage"])
def test_parse_ics_rejects_garbage(raw):
    try:
        d = gammu_calendar.parse_ics(raw)
    except ValueError:
        return
    assert d["events"] == [] and d["todos"] == []


def test_parse_ics_size_limit():
    with pytest.raises(ValueError, match="8 MiB"):
        gammu_calendar.parse_ics(b"x" * (9 * 1024 * 1024))


def fake_gammu(tmp_path, body):
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    write_tool(bindir / "gammu", body)
    return bindir


GOOD = ("import sys\nargs = sys.argv[1:]\nassert args[:2] == ['--config', 'cfg'] and args[2] == 'backup' and args[-1] == '-yes'\n"
        f"assert args[3].endswith('.ics')\nopen(args[3], 'wb').write({ICS!r})\n")


def run_cli(env_path, *args):
    env = dict(os.environ, PYTHONPATH=str(REPO), PATH=f"{env_path}:{os.environ['PATH']}")
    env.pop("SYMPORT_GAMMU_CONFIG", None)
    return subprocess.run([sys.executable, "-m", "symport", *args, "--json"], capture_output=True, text=True,
                          cwd=REPO, env=env)


def test_calendar_read_with_fake_gammu(tmp_path):
    bindir = fake_gammu(tmp_path, GOOD)
    r = run_cli(bindir, "phone", "calendar", "read", "--gammu-config", "cfg")
    d = json.loads(r.stdout)
    assert r.returncode == 0 and len(d["data"]["calendar"]["events"]) == 2
    ids = {c["id"]: c for c in d["checks"]}
    assert ids["calendar.compat"]["status"] == "unknown"                  # never claims E52 support
    assert d["verification"]["physical_device"] == "not-tested"


def test_calendar_empty_export_is_ambiguous_not_success(tmp_path):
    bindir = fake_gammu(tmp_path, "import sys\nopen(sys.argv[4], 'wb').write(b'')")
    d = json.loads(run_cli(bindir, "phone", "calendar", "read", "--gammu-config", "cfg").stdout)
    assert d["status"] == "failed" and "empty" in d["checks"][-1]["message"]
    ics_no_entries = b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"
    bindir = fake_gammu(tmp_path / "x", f"import sys\nopen(sys.argv[4], 'wb').write({ics_no_entries!r})")
    d = json.loads(run_cli(bindir, "phone", "calendar", "read", "--gammu-config", "cfg").stdout)
    assert any(c["id"] == "calendar.read" and c["status"] == "warn" for c in d["checks"])


def test_calendar_gammu_failure_and_missing_config(tmp_path):
    bindir = fake_gammu(tmp_path, "import sys; sys.exit(3)")
    r = run_cli(bindir, "phone", "calendar", "read", "--gammu-config", "cfg")
    assert r.returncode == 1 and json.loads(r.stdout)["status"] == "failed"
    r = run_cli(bindir, "phone", "calendar", "read")
    d = json.loads(r.stdout)
    assert r.returncode == 3 and d["status"] == "unsupported" and "Gammu" in d["data"]["unsupported_reason"]


def test_calendar_without_gammu_binary_is_unsupported(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(REPO), PATH="/usr/bin:/bin")
    r = subprocess.run([sys.executable, "-m", "symport", "phone", "calendar", "read", "--gammu-config", "x", "--json"],
                       capture_output=True, text=True, cwd=REPO, env=env)
    if r.returncode != 3:                       # a system gammu exists on this host: nothing to assert
        pytest.skip("gammu installed on the host")
    assert json.loads(r.stdout)["status"] == "unsupported"


def test_device_manager_exposes_inventory_and_calendar(tmp_path, monkeypatch):
    from symport.phone import DeviceManager
    from symport.phone.local import LocalTransports
    vol = tmp_path / "card"
    (vol / "Installs").mkdir(parents=True)
    (vol / "Installs" / "p.sis").write_bytes((FIX / "sdk_probe_package.sis").read_bytes())
    monkeypatch.setenv("SYMPORT_DEVICE_ROOTS", json.dumps({"e52-card": str(vol)}))
    monkeypatch.delenv("SYMPORT_GAMMU_CONFIG", raising=False)
    mgr = DeviceManager(tmp_path, LocalTransports())
    inv = mgr.execute({"action": "apps-inventory", "device": "e52-card"})
    assert inv["packages"][0]["name"] == "Symbian E32 Probe"
    with pytest.raises(ValueError, match="Unknown or disconnected"):
        mgr.execute({"action": "apps-inventory", "device": "nope"})
    with pytest.raises(ValueError):
        mgr.execute({"action": "apps-inventory", "device": 5})
    info = mgr.execute({"action": "discover"})
    assert "calendar" in info["limitations"] and "iCalendar export" in info["limitations"]["calendar"]
    with pytest.raises(ValueError, match="Gammu"):
        mgr.execute({"action": "calendar-read", "device": "gammu"})
    log = (tmp_path / "build" / "symport" / "device-manager" / "operations.jsonl").read_text()
    assert "SIS" not in log and "Symbian" not in log          # journal never keeps payload data
