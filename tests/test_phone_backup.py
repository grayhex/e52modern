import hashlib
import json
import os

import pytest

from symport.phone import archive


def make_volume(root):
    (root / "Images").mkdir(parents=True)
    (root / "Sounds" / "Digital").mkdir(parents=True)
    (root / "Images" / "фото 1.jpg").write_bytes(os.urandom(3000))
    (root / "Sounds" / "Digital" / "ring.mp3").write_bytes(b"mp3-bytes" * 500)
    (root / "empty.txt").write_bytes(b"")
    (root / "notes.txt").write_text("hello")
    return root


@pytest.fixture
def vol(tmp_path):
    return make_volume(tmp_path / "card")


def test_create_verify_roundtrip(vol, tmp_path):
    res = archive.create(vol, tmp_path / "bk", label="e52-card")
    assert res.complete and res.files == 4
    v = archive.verify(tmp_path / "bk")
    assert v["ok"] and v["checked"] == 4 and v["complete_at_creation"]
    m = archive.load_manifest(tmp_path / "bk")
    assert m["source_label"] == "e52-card" and m["totals"]["files"] == 4
    assert str(vol) not in json.dumps(m)                  # absolute source path is never stored
    src = vol / "Images" / "фото 1.jpg"
    dst = tmp_path / "bk" / "files" / "Images" / "фото 1.jpg"
    assert dst.read_bytes() == src.read_bytes() and dst.stat().st_mtime_ns == src.stat().st_mtime_ns


def test_symlinks_and_specials_are_skipped_not_followed(vol, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    os.symlink(outside, vol / "Images" / "link.jpg")
    os.symlink(tmp_path, vol / "linkdir")
    res = archive.create(vol, tmp_path / "bk")
    assert not res.complete
    assert {s.path for s in res.skipped} == {"Images/link.jpg", "linkdir"}
    assert not (tmp_path / "bk" / "files" / "linkdir").exists()
    assert archive.verify(tmp_path / "bk")["complete_at_creation"] is False


def test_exclude_and_limits(vol, tmp_path):
    res = archive.create(vol, tmp_path / "bk", exclude=("Sounds",))
    assert res.files == 3 and any(s.reason == "excluded by request" for s in res.skipped)
    with pytest.raises(archive.BackupError, match="limits"):
        archive.create(vol, tmp_path / "bk2", max_files=2)
    with pytest.raises(archive.BackupError, match="limits"):
        archive.create(vol, tmp_path / "bk3", max_bytes=10)


def test_refuses_unsafe_destinations(vol, tmp_path):
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "x").write_text("x")
    with pytest.raises(archive.BackupError, match="not empty"):
        archive.create(vol, tmp_path / "full")
    with pytest.raises(archive.BackupError, match="inside the source"):
        archive.create(vol, vol / "backup")
    with pytest.raises(archive.BackupError, match="not a directory"):
        archive.create(tmp_path / "missing", tmp_path / "bk")
    link = tmp_path / "linkvol"
    os.symlink(vol, link)
    with pytest.raises(archive.BackupError, match="symlink"):
        archive.create(link, tmp_path / "bk")


def test_not_enough_space_is_reported_before_copying(vol, tmp_path, monkeypatch):
    class U:
        free = 100
    monkeypatch.setattr(archive.shutil, "disk_usage", lambda p: U)
    with pytest.raises(archive.BackupError, match="free space"):
        archive.create(vol, tmp_path / "bk")


def test_file_changing_during_copy_is_not_recorded(vol, tmp_path, monkeypatch):
    real = archive._copy_hashed

    def lying(src, dst):
        digest, n = real(src, dst)
        return digest, n + 1
    monkeypatch.setattr(archive, "_copy_hashed", lying)
    res = archive.create(vol, tmp_path / "bk")
    assert res.files == 0 and len(res.skipped) == 4
    assert all("changed while" in s.reason for s in res.skipped)


def test_verify_detects_damage(vol, tmp_path):
    archive.create(vol, tmp_path / "bk")
    root = tmp_path / "bk" / "files"
    (root / "notes.txt").write_text("HELLO")             # same size, different content
    (root / "empty.txt").unlink()
    (root / "extra.bin").write_bytes(b"x")
    v = archive.verify(tmp_path / "bk")
    assert not v["ok"] and v["mismatched"] == ["notes.txt"] and v["missing"] == ["empty.txt"] and v["extra"] == ["extra.bin"]


def test_manifest_tampering_and_garbage(vol, tmp_path):
    archive.create(vol, tmp_path / "bk")
    mp = tmp_path / "bk" / "manifest.json"
    original = mp.read_text()
    mp.write_text(original.replace('"notes.txt"', '"other.txt"'))
    with pytest.raises(archive.BackupError, match="manifest.sha256"):
        archive.load_manifest(tmp_path / "bk")
    mp.write_text(original)
    (tmp_path / "bk" / "manifest.sha256").unlink()
    with pytest.raises(archive.BackupError, match="cannot trust"):
        archive.load_manifest(tmp_path / "bk")
    with pytest.raises(archive.BackupError, match="not a SymPort backup"):
        archive.load_manifest(tmp_path)
    mp.write_text("{not json")
    (tmp_path / "bk" / "manifest.sha256").write_text(hashlib.sha256(b"{not json").hexdigest() + "  manifest.json\n")
    with pytest.raises(archive.BackupError, match="not valid JSON"):
        archive.load_manifest(tmp_path / "bk")


def test_restore_plan_apply_and_never_overwrite(vol, tmp_path):
    archive.create(vol, tmp_path / "bk")
    target = tmp_path / "new-card"
    target.mkdir()
    (target / "notes.txt").write_text("hello")           # identical
    (target / "empty.txt").write_text("not empty")       # conflict
    plan = archive.restore(tmp_path / "bk", target)
    assert plan["plan"] == {"new": 2, "identical": 1, "conflict": 1, "blocked": 0} and not plan["applied"]
    assert not (target / "Images").exists()              # dry run writes nothing
    res = archive.restore(tmp_path / "bk", target, apply=True)
    assert res["written"] == 2 and res["verified"] == 2 and not res["failed"]
    assert (target / "empty.txt").read_text() == "not empty"             # conflict untouched
    assert (target / "Sounds" / "Digital" / "ring.mp3").read_bytes() == b"mp3-bytes" * 500
    again = archive.restore(tmp_path / "bk", target, apply=True)
    assert again["written"] == 0 and again["plan"]["identical"] == 3


def test_restore_only_prefix_and_refuses_damaged_backup(vol, tmp_path):
    archive.create(vol, tmp_path / "bk")
    t = tmp_path / "t"
    t.mkdir()
    res = archive.restore(tmp_path / "bk", t, apply=True, only="Sounds")
    assert res["written"] == 1 and not (t / "Images").exists()
    (tmp_path / "bk" / "files" / "notes.txt").write_text("tampered")
    t2 = tmp_path / "t2"
    t2.mkdir()
    with pytest.raises(archive.BackupError, match="failed verification"):
        archive.restore(tmp_path / "bk", t2, apply=True)
    assert not any(t2.iterdir())


def forge(bk, path):
    """Rewrite a valid-looking manifest containing an attacker-chosen path."""
    mp = bk / "manifest.json"
    m = json.loads(mp.read_text())
    m["files"][0]["path"] = path
    raw = json.dumps(m).encode()
    mp.write_bytes(raw)
    (bk / "manifest.sha256").write_text(hashlib.sha256(raw).hexdigest() + "  manifest.json\n")


@pytest.mark.parametrize("bad", ["../escape.txt", "/etc/passwd", "a/../../b", "C:evil", "dir\\file", "x/../y", "name .", "CON"])
def test_manifest_paths_cannot_escape_the_target(vol, tmp_path, bad):
    archive.create(vol, tmp_path / "bk")
    forge(tmp_path / "bk", bad)
    t = tmp_path / "t"
    t.mkdir()
    try:
        res = archive.restore(tmp_path / "bk", t)
        assert res["plan"]["blocked"] >= 1 and res["plan"]["new"] == 3
    except archive.BackupError as e:
        assert "unsafe" in str(e)
    assert not (tmp_path / "escape.txt").exists()
    v = archive.verify(tmp_path / "bk")
    assert not v["ok"]


def test_parent_component_that_is_a_file_is_blocked(vol, tmp_path):
    archive.create(vol, tmp_path / "bk")
    t = tmp_path / "t"
    t.mkdir()
    (t / "Images").write_text("a file where a folder is needed")
    res = archive.restore(tmp_path / "bk", t)
    assert res["plan"]["blocked"] == 1 and res["plan"]["new"] == 3
    assert any(b["path"].startswith("Images/") for b in res["details"]["blocked"])


def test_restore_space_check(vol, tmp_path, monkeypatch):
    archive.create(vol, tmp_path / "bk")
    t = tmp_path / "t"
    t.mkdir()

    class U:
        free = 10
    monkeypatch.setattr(archive.shutil, "disk_usage", lambda p: U)
    with pytest.raises(archive.BackupError, match="free space"):
        archive.restore(tmp_path / "bk", t, apply=True)
