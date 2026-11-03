"""Real media I/O and stateful mock Gammu. No physical-device compatibility claim."""

from __future__ import annotations

import base64
import copy
import io
import json
import zipfile
from datetime import datetime

import pytest
from PIL import Image

from symport.phone import DeviceManager
from symport.phone import gammu_native as native
from symport.phone.local import LocalTransports
from symport.phone.media import execute as media_execute
from symport.phone.media_downloads import MediaDownloads, byte_range
from symport.phone.personal import PersonalWorkspace, calendar_import, update_record
from tests.test_web import _http, http_server, repo  # noqa: F401


class MockPhone:
    """Test-only phone with persistent stores and optional failure/read-back drift."""

    def __init__(self):
        self.identity = {
            "model": "Test phone",
            "firmware": "fixture",
            "fingerprint": "test-phone-fingerprint",
            "write_identity": True,
        }
        self.records = {
            "contacts": [
                {
                    "Location": 1,
                    "MemoryType": "ME",
                    "Entries": [
                        {"Type": "Text_Name", "Value": "Private Contact"},
                        {"Type": "Number_Mobile", "Value": "+123456789", "Location": "Work"},
                        {"Type": "Text_Email", "Value": "private@example.test"},
                        {"Type": "Text_Note", "Value": "Preserve this note"},
                    ],
                }
            ],
            "calendar": [
                {
                    "Location": 1,
                    "Type": "MEETING",
                    "Entries": [
                        {"Type": "TEXT", "Value": "Private appointment"},
                        {"Type": "START_DATETIME", "Value": datetime(2030, 1, 2, 9)},
                        {"Type": "END_DATETIME", "Value": datetime(2030, 1, 2, 10)},
                        {"Type": "LOCATION", "Value": "Room 1"},
                    ],
                }
            ],
            "tasks": [
                {
                    "Location": 1,
                    "Type": "MEMO",
                    "Priority": "None",
                    "Entries": [{"Type": "TEXT", "Value": "Private task"}],
                }
            ],
            "sms": [
                {
                    "Location": 1,
                    "Folder": 1,
                    "Number": "+123456789",
                    "Text": "=PRIVATE-SMS",
                    "Type": "Deliver",
                    "State": "UnRead",
                    "DateTime": datetime(2030, 1, 2, 8),
                    "UDH": {},
                }
            ],
        }
        self.writes, self.fail, self.drift = 0, False, False

    def invoke(self, config, action, **data):
        domain = data.get("domain")
        if action == "details":
            return dict(
                self.identity,
                capability_status={k: {"status": "available"} for k in self.records},
                sms_send_verified=False,
            )
        if action == "read":
            return copy.deepcopy({"identity": self.identity, "records": self.records[domain]})
        if action == "imei":
            return {"imei": "000000000000000"}
        if action == "write":
            self.writes += 1
            if self.fail:
                raise ValueError("Test-only failure")
            record = copy.deepcopy(data["record"])
            if record.get("Location"):
                index = next(
                    i
                    for i, r in enumerate(self.records[domain])
                    if r["Location"] == record["Location"]
                )
                assert native.digest(self.records[domain][index]) == data["before_hash"]
                self.records[domain][index] = record
            else:
                record["Location"] = max([r["Location"] for r in self.records[domain]] + [0]) + 1
                self.records[domain].append(record)
            if self.drift:
                record["Entries"] = []
            return {"record": copy.deepcopy(record), "location": record["Location"]}
        if action == "send":
            raise ValueError("Sending not enrolled in this test")
        raise ValueError("Unknown test operation")


@pytest.fixture
def personal(tmp_path):
    phone = MockPhone()
    return PersonalWorkspace(tmp_path, phone.invoke), phone


def read(workspace, domain="contacts"):
    return workspace.execute("test", {"action": "personal-read", "domain": domain})


def preview(workspace, result, rows):
    return workspace.execute(
        "test", {"action": "personal-preview", "snapshot": result["snapshot"], "rows": rows}
    )


def apply(workspace, result, plan, confirm=True):
    return workspace.execute(
        "test",
        {
            "action": "personal-apply",
            "snapshot": result["snapshot"],
            "plan": plan["plan"],
            "confirm": confirm,
        },
    )


def test_contact_preview_backup_preservation_and_no_replay(personal):
    workspace, phone = personal
    result = read(workspace)
    row = dict(result["rows"][0], phones=["+987654321"])
    plan = preview(workspace, result, [row])
    assert phone.writes == 0 and plan["dry_run"] and plan["deletions"] == 0
    with pytest.raises(ValueError, match="Confirm"):
        apply(workspace, result, plan, False)
    done = apply(workspace, result, plan)
    assert done["status"] == "verified-by-readback" and done["verified"] == 1
    entries = phone.records["contacts"][0]["Entries"]
    assert any(e["Type"] == "Text_Note" for e in entries)
    assert next(e for e in entries if e["Type"].startswith("Number_")) == {
        "Type": "Number_Mobile",
        "Value": "+987654321",
        "Location": "Work",
    }
    backup = workspace.root / (done["backup"] + ".json")
    assert "+123456789" in backup.read_text() and (backup.stat().st_mode & 0o077) == 0
    with pytest.raises(ValueError):
        apply(workspace, result, plan)
    assert phone.writes == 1


def test_identity_change_conflicts_and_partial_no_retry(personal):
    workspace, phone = personal
    result = read(workspace)
    plan = preview(workspace, result, [dict(result["rows"][0], name="Changed")])
    phone.identity["fingerprint"] = "other-phone"
    with pytest.raises(ValueError, match="changed"):
        apply(workspace, result, plan)
    assert phone.writes == 0
    phone.identity["fingerprint"] = "test-phone-fingerprint"
    phone.fail = True
    done = apply(workspace, result, plan)
    assert done["status"] == "partial-or-unverified" and done["backup"]
    with pytest.raises(ValueError):
        apply(workspace, result, plan)
    assert phone.writes == 1


def test_duplicates_and_changed_phone_before_preview(personal):
    workspace, phone = personal
    phone.records["contacts"].append(dict(copy.deepcopy(phone.records["contacts"][0]), Location=2))
    result = read(workspace)
    assert result["duplicates"] == [[0, 1]]
    row = dict(result["rows"][0])
    row.pop("native_id")
    plan = preview(workspace, result, [row, row])
    assert plan["changes"] == [] and plan["skipped"] == 2
    with pytest.raises(ValueError, match="only once"):
        preview(workspace, result, [result["rows"][0], result["rows"][0]])
    phone.records["contacts"][0]["Entries"][0]["Value"] = "Changed on phone"
    with pytest.raises(ValueError, match="changed"):
        preview(workspace, result, [row])


def test_calendar_tasks_conflicts_timezone_and_readback(personal):
    workspace, phone = personal
    result = read(workspace, "calendar")
    row = dict(result["rows"][0], summary="Updated event")
    plan = preview(workspace, result, [row])
    assert apply(workspace, result, plan)["status"] == "verified-by-readback"
    result = read(workspace, "calendar")
    new = dict(result["rows"][0])
    new.pop("native_id")
    new["summary"] = "Conflicting import"
    assert preview(workspace, result, [new])["conflicts"]
    with pytest.raises(ValueError, match="timezone"):
        preview(workspace, result, [dict(result["rows"][0], start="2030-01-02T09:00:00+03:00")])
    with pytest.raises(ValueError, match="Recurring"):
        update_record(
            dict(
                phone.records["calendar"][0],
                Entries=phone.records["calendar"][0]["Entries"]
                + [{"Type": "REPEAT_FREQUENCY", "Value": 1}],
            ),
            row,
            "calendar",
        )
    result = read(workspace, "tasks")
    plan = preview(workspace, result, [dict(result["rows"][0], completed=True)])
    phone.drift = True
    assert apply(workspace, result, plan)["status"] == "partial-or-unverified"


def test_exports_private_logs_and_no_mass_storage_pim(personal, tmp_path, monkeypatch):
    workspace, phone = personal
    result = read(workspace, "sms")
    exported = workspace.execute(
        "test", {"action": "personal-export", "snapshot": result["snapshot"], "format": "csv"}
    )
    csv = base64.b64decode(exported["content"]).decode()
    assert "'=PRIVATE-SMS" in csv and "'+123456789" in csv
    result = read(workspace)
    exported = workspace.execute(
        "test", {"action": "personal-export", "snapshot": result["snapshot"], "format": "vcf"}
    )
    assert "BEGIN:VCARD" in base64.b64decode(exported["content"]).decode()
    local = LocalTransports(tmp_path)
    local.personal = workspace
    monkeypatch.setenv("SYMPORT_GAMMU_CONFIG", "test")
    manager = DeviceManager(tmp_path, local)
    manager.execute({"action": "personal-read", "device": "gammu", "domain": "sms"})
    log = manager.journal.read_text()
    assert all(
        s not in log
        for s in ("PRIVATE-SMS", "123456789", "Private Contact", "fingerprint", "snapshot")
    )
    with pytest.raises(ValueError):
        manager.execute({"action": "personal-read", "device": "card", "domain": "sms"})
    phone.identity["write_identity"] = False
    result = read(workspace)
    with pytest.raises(ValueError, match="uniquely"):
        preview(workspace, result, [dict(result["rows"][0], name="New")])


def test_icalendar_import_marks_advanced_fields_and_preserves_uid():
    raw = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:stable-uid\r\nSUMMARY:Meeting\r\nDTSTART:20300102T090000\r\nRRULE:FREQ=DAILY\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    row = calendar_import(raw)[0]
    assert (
        row["uid"] == "stable-uid"
        and row["start"] == "2030-01-02T09:00:00"
        and row["unsupported"] == ["rrule"]
    )
    with pytest.raises(ValueError):
        update_record(None, row, "calendar")


class ERR_EMPTY(Exception):
    pass


def test_native_iteration_uses_documented_locations_and_rejects_partial():
    class SM:
        def GetMemoryStatus(self, Type):
            assert Type == "ME"
            return {"Used": 2}

        def GetNextMemory(self, Type, Start=False, Location=None):
            assert Type == "ME"
            if Start:
                return {"Location": 1}
            if Location == 1:
                return {"Location": 5}
            raise ERR_EMPTY()

    assert [r["Location"] for r in native.read_records(SM(), "contacts")] == [1, 5]

    class Partial(SM):
        def GetMemoryStatus(self, Type):
            return {"Used": 3}

    with pytest.raises(ERR_EMPTY):
        native.read_records(Partial(), "contacts")

    class Empty(SM):
        def GetMemoryStatus(self, Type):
            return {"Used": 0}

    assert native.read_records(Empty(), "contacts") == []


def test_media_recursive_thumbnail_revision_and_private_zip(tmp_path, monkeypatch):
    root = tmp_path / "phone"
    (root / "Images").mkdir(parents=True)
    Image.new("RGB", (640, 480), "blue").save(root / "Images/a.jpg")
    (root / "music.mp3").write_bytes(b"ID3" + b"x" * 600000)
    (root / "secret.txt").write_text("not media")
    (root / "escape.jpg").symlink_to(tmp_path / "outside.jpg")
    monkeypatch.setenv("SYMPORT_DEVICE_ROOTS", json.dumps({"card": str(root)}))
    manager = DeviceManager(tmp_path)
    items = manager.execute({"action": "media-list", "device": "card"})["items"]
    assert {i["path"] for i in items} == {"Images/a.jpg", "music.mp3"}
    photo = next(i for i in items if i["kind"] == "photo")
    args = {"device": "card", "path": photo["path"], "revision": photo["revision"]}
    thumbnail = manager.execute(dict(args, action="media-thumbnail"))
    with Image.open(io.BytesIO(base64.b64decode(thumbnail["content"]))) as image:
        assert image.size == (320, 240) and not image.getexif()
    downloads = MediaDownloads(tmp_path, manager)
    exported = downloads.export({"device": "card", "items": items})
    path = downloads.archive(exported["url"].rsplit("/", 1)[-1])
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == {"Images/a.jpg", "music.mp3"}
        assert archive.read("music.mp3") == (root / "music.mp3").read_bytes()
    assert path.stat().st_mode & 0o077 == 0
    (root / "Images/a.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        manager.execute(dict(args, action="media-chunk", offset=0, limit=100))
    with pytest.raises(ValueError):
        media_execute(
            manager.transport.files, dict(args, path="../outside.jpg", action="media-info")
        )


def test_ranges_and_cookie_authorization(http_server, tmp_path):  # noqa: F811
    state, port = http_server
    root = tmp_path / "media"
    root.mkdir()
    (root / "a.mp4").write_bytes(b"0123456789")
    local = LocalTransports(tmp_path)
    local.files.roots = {"card": root}
    state.devices.transport = local
    meta = state.devices.execute({"action": "media-list", "device": "card"})["items"][0]
    from urllib.parse import urlencode

    url = "/api/media/file?" + urlencode(
        {"device": "card", "path": "a.mp4", "revision": meta["revision"]}
    )
    assert _http(port, "GET", url)[0] == 403
    cookie = {"Cookie": f"symport_media={state.token}"}
    status, raw = _http(port, "GET", url, headers=dict(cookie, Range="bytes=2-5"))
    assert status == 206 and raw == b"2345"
    assert _http(port, "GET", url, headers=dict(cookie, Range="bytes=99-"))[0] == 416
    assert (
        _http(port, "GET", url, headers=dict(cookie, **{"Sec-Fetch-Site": "cross-site"}))[0] == 403
    )
    assert byte_range("bytes=-3", 10) == (7, 9, 206)
    assert byte_range("bytes=3-", 10) == (3, 9, 206)
    for value in ("bytes=1-2,4-5", "bytes=-0", "bytes=5-1"):
        with pytest.raises(ValueError):
            byte_range(value, 10)
