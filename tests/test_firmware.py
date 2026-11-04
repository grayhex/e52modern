"""Firmware & ROM Explorer: indexing, search, inspection, dependencies and comparison."""
from __future__ import annotations

import io
import json
import struct
import time
import zipfile

import pytest

from symport.firmware import FirmwareError, FirmwareExplorer, formats
from symport.firmware.rom import RomError, RomImage
from tests.helpers import REPO, make_e32
from tests.test_web import http_server, repo  # noqa: F401

MBM = (REPO / "theme/dist/light/e52clearlight.mbm").read_bytes()
MIF = (REPO / "theme/dist/light/e52clearlight.mif").read_bytes()


def zip_bytes(members, nest="fw/Z/"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(nest + name, data)
    return buffer.getvalue()


def firmware(version="1"):
    app = make_e32(uid3=0x20001001, imports={"euser.dll": [1, 2], "helper.dll": [3], "gone.dll": [4]}, caps_low=1 << 13)
    return {
        "sys/bin/app.exe": app,
        "sys/bin/helper.dll": make_e32(dll=True, uid3=0x20001002, imports={"euser.dll": [1]}),
        "sys/bin/euser.dll": make_e32(dll=True, uid3=0x100039E5),
        "sys/bin/packed.dll": make_e32(dll=True, compression=0x101F7AFC),
        "resource/skins/t.mbm": MBM,
        "resource/apps/t.mif": MIF,
        "resource/apps/app.rsc": b"\x01\x02\x03" + version.encode(),
        "private/10003a3f/import/apps/app_reg.rsc": b"reg",
    }


def wait(fx, key):
    for _ in range(100):
        meta = fx.execute({"action": "status", "id": key})
        if meta["status"] != "indexing":
            return meta
        time.sleep(0.05)
    raise AssertionError("indexing did not finish")


@pytest.fixture
def fx(tmp_path):
    return FirmwareExplorer(tmp_path / "fw")


def upload(fx, data, name="firmware.zip"):
    meta = fx.store.create(io.BytesIO(data), len(data), name)
    return meta["id"], wait(fx, meta["id"])


def test_zip_index_counts_kinds_and_strips_wrapper_folder(fx):
    key, meta = upload(fx, zip_bytes(firmware()))
    assert meta["status"] == "ready" and meta["files"] == 8
    assert meta["counts"]["by_kind"]["e32-dll"] == 3 and meta["counts"]["by_kind"]["e32-exe"] == 1
    assert meta["counts"]["by_kind"]["mbm"] == 1 and meta["counts"]["by_kind"]["mif"] == 1
    assert meta["levels"]["boot"] == "not-tested" and meta["levels"]["physical_device"] == "not-tested"
    top = fx.execute({"action": "children", "id": key, "dir": "Z:"})
    assert [f["name"] for f in top["folders"]] == ["private", "resource", "sys"]
    sysbin = fx.execute({"action": "children", "id": key, "dir": "z:/sys/bin"})
    assert {f["name"] for f in sysbin["files"]} == {"app.exe", "helper.dll", "euser.dll", "packed.dll"}
    assert fx.execute({"action": "children", "id": key, "dir": "Z:/nothing"})["files"] == []
    with pytest.raises(FirmwareError):
        fx.execute({"action": "children", "id": key, "dir": "Z:/../etc"})


def test_search_and_filters(fx):
    key, _ = upload(fx, zip_bytes(firmware()))
    assert fx.execute({"action": "search", "id": key, "query": "HELPER"})["total"] == 1
    assert fx.execute({"action": "search", "id": key, "kind": "e32-dll"})["total"] == 3
    assert fx.execute({"action": "search", "id": key, "capability": "NetworkServices"})["entries"][0]["name"] == "app.exe"
    assert fx.execute({"action": "search", "id": key, "uid": "20001002"})["entries"][0]["name"] == "helper.dll"
    assert fx.execute({"action": "search", "id": key, "limit": 2})["entries"].__len__() == 2
    for bad in ({"limit": 0}, {"limit": 10_000}, {"offset": -1}):
        with pytest.raises(FirmwareError):
            fx.execute({"action": "search", "id": key, **bad})


def test_file_metadata_for_e32_mbm_mif_and_unknown(fx):
    key, _ = upload(fx, zip_bytes(firmware()))
    exe = fx.execute({"action": "file", "id": key, "path": "Z:/sys/bin/app.exe"})
    assert exe["e32_full"]["uids"][2] == "0x20001001" and exe["entry"]["e32"]["imports"] == ["euser.dll", "helper.dll", "gone.dll"]
    assert exe["hex_head"][32:40] == b"EPOC".hex()
    mbm = fx.execute({"action": "file", "id": key, "path": "z:/resource/skins/t.mbm"})["entry"]
    assert mbm["kind"] == "mbm" and mbm["mbm"]["count"] == 71 and mbm["mbm"]["bitmaps"][0]["width"] == 240
    mif = fx.execute({"action": "file", "id": key, "path": "Z:/resource/apps/t.mif"})["entry"]
    assert mif["kind"] == "mif" and mif["mif"]["format_version"] == 2
    rsc = fx.execute({"action": "file", "id": key, "path": "Z:/resource/apps/app.rsc"})["entry"]
    assert rsc["kind"] == "resource" and rsc["basis"] == "extension"
    with pytest.raises(FirmwareError):
        fx.execute({"action": "file", "id": key, "path": "Z:/missing"})


def test_dependencies_resolve_against_the_image_and_unknown_stays_unknown(fx):
    key, _ = upload(fx, zip_bytes(firmware()))
    deps = fx.execute({"action": "dependencies", "id": key, "path": "Z:/sys/bin/app.exe"})
    status = {d["name"]: d["status"] for d in deps["imports"]}
    assert status == {"euser.dll": "present-in-image", "helper.dll": "present-in-image", "gone.dll": "missing-from-image"}
    assert fx.execute({"action": "dependencies", "id": key, "path": "Z:/sys/bin/euser.dll"})["imported_by"] == [
        "Z:/sys/bin/app.exe", "Z:/sys/bin/helper.dll"]
    packed = fx.execute({"action": "dependencies", "id": key, "path": "Z:/sys/bin/packed.dll"})
    assert packed["imports_known"] is False and packed["imports"] is None and "not available" in packed["note"]


def test_compare_reports_added_removed_changed_and_e32_details(fx):
    a, _ = upload(fx, zip_bytes(firmware("1")), "a.zip")
    changed = firmware("2")
    changed["sys/bin/app.exe"] = make_e32(uid3=0x20001001, imports={"euser.dll": [1, 2], "newdep.dll": [3]}, caps_low=(1 << 13) | (1 << 15))
    changed["sys/bin/extra.dll"] = make_e32(dll=True)
    del changed["resource/apps/t.mif"]
    b, _ = upload(fx, zip_bytes(changed), "b.zip")
    result = fx.execute({"action": "compare", "a": a, "b": b})
    assert result["summary"] == {"only_a": 1, "only_b": 1, "changed": 2, "identical": 5, "e32_changed": 1}
    assert result["only_a"] == ["Z:/resource/apps/t.mif"] and result["only_b"] == ["Z:/sys/bin/extra.dll"]
    exe = next(c for c in result["changed"] if c["path"].endswith("app.exe"))
    assert exe["details"]["capabilities"] == {"added": ["ReadUserData"], "removed": []}
    assert exe["details"]["imports"] == {"added": ["newdep.dll"], "removed": ["gone.dll", "helper.dll"]}


def test_profile_export_feeds_dependency_analysis(fx, tmp_path):
    key, _ = upload(fx, zip_bytes(firmware()))
    profile = fx.execute({"action": "profile", "id": key, "firmware_version": "RM-000 test"})
    assert profile["schema"] == 1 and set(profile["dlls"]) == {"helper.dll", "euser.dll", "packed.dll"}
    assert profile["source"].startswith("firmware-explorer:")
    names, source = fx.dll_names(key)
    assert names == set(profile["dlls"]) and source.startswith("firmware-explorer:")
    with pytest.raises(FirmwareError):
        fx.execute({"action": "profile", "id": key, "firmware_version": ""})


def test_unsafe_and_encrypted_members_are_skipped_not_extracted(fx):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Z/sys/bin/ok.dll", make_e32(dll=True))
        archive.writestr("../evil.dll", b"x")
        archive.writestr("Z/a/../../b.dll", b"x")
    key, meta = upload(fx, buffer.getvalue())
    assert meta["files"] == 1 and meta["skipped_count"] == 2
    assert not (fx.store.root.parent / "evil.dll").exists()


def test_rejected_inputs_and_limits(fx, monkeypatch):
    for data, text in ((b"", "Upload between"), (b"\x00" * 4096, "Unsupported firmware file")):
        with pytest.raises(FirmwareError, match=text):
            fx.store.create(io.BytesIO(data), len(data), "x.bin")
    with pytest.raises(FirmwareError, match="safe characters"):
        fx.store.create(io.BytesIO(b"PK"), 2, "../x.zip")
    with pytest.raises(FirmwareError, match="Upload ended early"):
        fx.store.create(io.BytesIO(b"PK\x03\x04"), 99, "x.zip")
    assert fx.execute({"action": "list"})["images"] == []          # failed uploads leave nothing behind
    monkeypatch.setenv("SYMPORT_FIRMWARE_MAX_MB", "1")
    with pytest.raises(FirmwareError, match="Upload between"):
        fx.store.create(io.BytesIO(b"x"), 2 * 1024 * 1024, "big.zip")
    broken = fx.store.create(io.BytesIO(b"PK\x03\x04" + b"junk"), 8, "broken.zip")
    assert wait(fx, broken["id"])["status"] == "failed"
    with pytest.raises(FirmwareError, match="failed"):
        fx.execute({"action": "children", "id": broken["id"]})
    for bad in ("../x", "ZZ", "a" * 15, None):
        with pytest.raises(FirmwareError, match="Invalid firmware ID"):
            fx.execute({"action": "status", "id": bad})
    with pytest.raises(FirmwareError, match="Unknown firmware operation"):
        fx.execute({"action": "run", "id": broken["id"]})


def test_delete_requires_confirmation(fx):
    key, _ = upload(fx, zip_bytes(firmware()))
    with pytest.raises(FirmwareError, match="confirmation"):
        fx.execute({"action": "delete", "id": key})
    assert fx.execute({"action": "delete", "id": key, "confirm": True}) == {"deleted": key}
    assert fx.execute({"action": "list"})["images"] == []


def test_image_count_is_bounded(fx):
    data = zip_bytes({"sys/bin/a.dll": make_e32(dll=True)})
    for _ in range(6):
        upload(fx, data)
    with pytest.raises(FirmwareError, match="At most 6"):
        fx.store.create(io.BytesIO(data), len(data), "seventh.zip")


# ---- core ROM image (experimental reader, synthetic images only) ---------------------------------
def build_rom(files, base=0x80000000):
    """Core ROM image with TRomHeader/TRomEntry layout (see symport.firmware.rom)."""
    def entry(name, size, address, attribute):
        raw = struct.pack("<IIBB", size, address, attribute, len(name)) + name.encode("utf-16-le")
        return raw + b"\0" * (-len(raw) % 4)

    tree = {}
    for path, data in files.items():
        node = tree
        parts = path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = data
    body = bytearray(0x200)
    blobs = {}

    def place(data):
        body.extend(b"\0" * (-len(body) % 4))
        address = base + len(body)
        body.extend(data)
        return address

    def write_dir(node):
        entries = b""
        for name, value in sorted(node.items()):
            if isinstance(value, dict):
                entries += entry(name, 0, write_dir(value), 0x10)
            else:
                blobs[name] = place(value)
                entries += entry(name, len(value), blobs[name], 0x01)
        return place(struct.pack("<I", len(entries)) + entries)

    root = write_dir(tree)
    root_list = place(struct.pack("<III", 1, 0, root))
    struct.pack_into("<BBH", body, 128, 1, 2, 3)
    struct.pack_into("<III", body, 140, base, len(body), root_list)
    return bytes(body)


def test_core_rom_image_lists_directories_and_indexes_files(fx):
    image = build_rom({"sys/bin/app.exe": make_e32(), "sys/bin/x.dll": make_e32(dll=True), "resource/a.rsc": b"abc"})
    rom = RomImage(image)
    assert sorted(p for p, _a, _s in rom.entries()) == ["resource/a.rsc", "sys/bin/app.exe", "sys/bin/x.dll"]
    key, meta = upload(fx, image, "core.rom")
    assert meta["kind"] == "rom" and meta["files"] == 3 and meta["rom"]["version"] == "1.2.3"
    exe = fx.execute({"action": "file", "id": key, "path": "Z:/sys/bin/app.exe"})
    assert exe["entry"]["kind"] == "e32-exe" and exe["entry"]["e32"]["secure_id"]
    assert "experimental" in " ".join(meta["limitations"]).lower()


def test_rom_reader_rejects_garbage_and_loops():
    with pytest.raises(RomError):
        RomImage(b"\0" * 0x300)
    image = bytearray(build_rom({"a.dll": b"x"}))
    base = struct.unpack_from("<I", image, 140)[0]
    root_list = struct.unpack_from("<I", image, 148)[0]
    root = struct.unpack_from("<I", image, root_list - base + 8)[0]
    struct.pack_into("<I", image, root - base + 4 + 4, root)       # first entry points back to its own directory
    struct.pack_into("<B", image, root - base + 4 + 8, 0x10)
    with pytest.raises(RomError, match="loop|nesting"):
        list(RomImage(bytes(image)).entries())


def test_format_sniffers():
    assert formats.classify("x.bin", make_e32(dll=True)) == ("e32-dll", "magic")
    assert formats.classify("x.bin", MBM[:64]) == ("mbm", "magic")
    assert formats.classify("x.rsc", b"zzzz") == ("resource", "extension")
    assert formats.classify("x", b"") == ("other", "none")
    assert formats.mbm_info(MBM)["bitmaps"][0] == {"width": 240, "height": 320, "bits_per_pixel": 16, "color": True,
                                                   "palette_entries": 0, "compression": "rle16", "data_size": 87811}
    with pytest.raises(ValueError):
        formats.mbm_info(MBM[:20])
    with pytest.raises(ValueError):
        formats.mif_info(b"nope" * 4)


# ---- HTTP endpoints ------------------------------------------------------------------------------
def raw_http(port, path, body, content_type, token=None):
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": f"127.0.0.1:{port}", "Content-Type": content_type}
    if token:
        headers["X-Symport-Token"] = token
    conn.request("POST", path, body=body, headers=headers)
    response = conn.getresponse()
    result = response.status, json.loads(response.read() or b"{}")
    conn.close()
    return result


def test_http_firmware_upload_and_explorer(http_server):  # noqa: F811
    state, port = http_server
    data = zip_bytes(firmware())

    def call(body):
        return raw_http(port, "/api/firmware", json.dumps(body).encode(), "application/json", state.token)

    status, meta = raw_http(port, "/api/firmware/upload?name=fw.zip", data, "application/octet-stream", state.token)
    assert status == 200 and meta["status"] in ("indexing", "ready")
    for _ in range(100):
        status, info = call({"action": "status", "id": meta["id"]})
        if info["status"] != "indexing":
            break
        time.sleep(0.05)
    assert info["counts"]["files"] == 8
    assert raw_http(port, "/api/firmware/upload?name=fw.zip", data, "text/plain", state.token)[0] == 415
    assert raw_http(port, "/api/firmware/upload?name=..%2Fx.zip", data, "application/octet-stream", state.token)[0] == 400
    assert raw_http(port, "/api/firmware", b"{}", "application/json")[0] == 403
    assert raw_http(port, "/api/firmware/upload?name=fw.zip", data, "application/octet-stream")[0] == 403
    status, found = call({"action": "search", "id": meta["id"], "kind": "mbm"})
    assert status == 200 and found["total"] == 1
    status, refused = call({"action": "delete", "id": meta["id"]})
    assert status == 400 and "confirmation" in refused["error"]
