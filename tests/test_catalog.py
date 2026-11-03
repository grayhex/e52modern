from __future__ import annotations

import copy
import hashlib
import io
import json
import socket
import time
import zipfile
from pathlib import Path

import pytest

from symport.catalog.download import Downloader, Redirects, public_https
from symport.catalog.model import Catalog
from symport.catalog.packages import attributes, validate_package
from symport.catalog.service import AppCatalog
from symport.phone.files import MountedVolumes
from symport.phone.service import DeviceManager
from tests.test_web import _http, http_server, repo  # noqa: F401


def jar_bytes(name="Example"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(zipfile.ZipInfo("Main.class", (2004, 1, 1, 0, 0, 0)), b"\xca\xfe\xba\xbe")
        archive.writestr(
            zipfile.ZipInfo("META-INF/MANIFEST.MF", (2004, 1, 1, 0, 0, 0)),
            f"Manifest-Version: 1.0\r\nMIDlet-Name: {name}\r\nMIDlet-Version: 1.0\r\nMIDlet-Vendor: Test\r\nMIDlet-1: {name},,Main\r\nMicroEdition-Profile: MIDP-2.0\r\nMicroEdition-Configuration: CLDC-1.1\r\n",
        )
    return output.getvalue()


def public_address(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]


class FixtureOpener:
    def __init__(self, payload, final="https://release-assets.githubusercontent.com/file"):
        self.payload, self.final, self.calls = payload, final, 0

    def open(self, request, timeout):
        self.calls += 1
        result = io.BytesIO(self.payload)
        result.headers = {"Content-Length": str(len(self.payload))}
        result.geturl = lambda: self.final
        return result


def artifact(raw, name="Example.jar"):
    return {
        "name": name,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "publisher_sha256": None,
        "url": "https://github.com/author/project/releases/download/1/" + name,
    }


def catalog_fixture(root):
    base = json.loads(
        (Path(__file__).resolve().parents[1] / "catalog/apps/hotpants.json").read_text()
    )
    directory = root / "catalog"
    (directory / "apps").mkdir(parents=True)
    sources = {}
    for key in ["runtime", "example", "manual", "blocked"]:
        entry = dict(
            copy.deepcopy(base),
            id=key,
            name=key,
            source_id=key,
            dependencies=["runtime"] if key == "example" else [],
            format="jar",
            delivery="manual" if key == "manual" else "automatic",
            compatibility="unsupported" if key == "blocked" else "likely-compatible",
        )
        (directory / "apps" / (key + ".json")).write_text(json.dumps(entry))
        sources[key] = {"artifacts": [artifact(jar_bytes(key), key + ".jar")]}
    (directory / "sources.json").write_text(json.dumps(sources))
    (directory / "research.json").write_text("[]")
    return sources


def wait_job(service, key):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = service.job(key)
        if job["state"] != "running":
            return job
        time.sleep(0.01)
    pytest.fail("Catalog batch did not finish")


def test_curated_catalog_has_30_traceable_entries():
    catalog = Catalog(Path(__file__).resolve().parents[1] / "catalog")
    assert len(catalog.entries) >= 30
    assert sum(e["delivery"] == "automatic" for e in catalog.entries.values()) >= 10
    for entry in catalog.entries.values():
        assert entry["e52_evidence"] is None and entry["compatibility"] != "verified-on-e52"
        assert entry["source_id"] in catalog.sources
        for source in catalog.sources[entry["source_id"]]["artifacts"]:
            assert len(source["sha256"]) == 64 and source["size"] > 0
    assert catalog.list({"category": "documents", "network": "offline"})
    assert catalog.list({"query": "hotpants"})[0]["id"] == "hotpants"
    assert all(e["format"].startswith("jar") for e in catalog.list({"format": "jar"}))


def test_dependency_plan_manual_and_unknown_device(tmp_path):
    catalog_fixture(tmp_path)
    catalog = Catalog(tmp_path / "catalog")
    plan = catalog.plan(["example"])
    assert plan["ids"] == ["runtime", "example"] and plan["added_dependencies"] == ["runtime"]
    assert catalog.plan(["manual"])["problems"]
    assert catalog.plan(["blocked"])["problems"]
    catalog.entries["runtime"]["dependencies"] = ["example"]
    with pytest.raises(ValueError, match="cycle"):
        catalog.plan(["example"])
    with pytest.raises(ValueError):
        catalog.plan(["example"], "made-up-phone")


def test_source_schema_rejects_false_e52_claim(tmp_path):
    catalog_fixture(tmp_path)
    path = tmp_path / "catalog/apps/example.json"
    entry = json.loads(path.read_text())
    entry["compatibility"] = "verified-on-e52"
    path.write_text(json.dumps(entry))
    with pytest.raises(ValueError):
        Catalog(tmp_path / "catalog")


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a",
        "https://127.0.0.1/a",
        "https://evil.test/a",
        "https://github.com:8443/a",
        "https://user:secret@github.com/a",
    ],
)
def test_downloader_rejects_ssrf_urls(url):
    with pytest.raises(ValueError):
        public_https(url, resolver=public_address)


def test_private_dns_and_redirect_rejected():
    def private(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    with pytest.raises(ValueError):
        public_https("https://github.com/file", resolver=private)
    with pytest.raises(ValueError):
        Redirects().redirect_request(None, None, 302, "", {}, "http://127.0.0.1/private")


def test_download_cache_hash_and_corruption(tmp_path, monkeypatch):
    monkeypatch.setattr("symport.catalog.download.public_https", lambda url: None)
    raw = jar_bytes()
    source = {"artifacts": [artifact(raw)]}
    opener = FixtureOpener(raw)
    downloader = Downloader(tmp_path, opener)
    path, info = downloader.fetch(source, source["artifacts"][0])
    assert info["validation"]["format"] == "jar" and not info["cache_hit"]
    assert downloader.fetch(source, source["artifacts"][0])[1]["cache_hit"] and opener.calls == 1
    path.write_bytes(b"corrupt")
    assert (
        not downloader.fetch(source, source["artifacts"][0])[1]["cache_hit"] and opener.calls == 2
    )
    bad = copy.deepcopy(source)
    bad["artifacts"][0]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        downloader.fetch(bad, bad["artifacts"][0])
    assert not list(tmp_path.rglob(".download-*"))


def test_jar_jad_corruptions_and_pair_validation():
    jar = jar_bytes()
    jad = f"MIDlet-Name: Example\nMIDlet-Version: 1.0\nMIDlet-Vendor: Test\nMIDlet-Jar-URL: Example.jar\nMIDlet-Jar-Size: {len(jar)}\n".encode()
    assert validate_package("Example.jad", jad, ("Example.jar", jar))["paired"]
    with pytest.raises(ValueError, match="size mismatch"):
        validate_package("Example.jad", jad, ("Other.jar", jar))
    with pytest.raises(ValueError):
        validate_package("Bad.jar", b"not a jar")
    with pytest.raises(ValueError):
        validate_package("Bad.sis", b"not a sis")
    with pytest.raises(ValueError):
        attributes(b"MIDlet-Name: First\nMIDlet-Name: Second\n")


def test_batch_transfer_mock_dependencies_retry_and_manual_confirmation(tmp_path):
    catalog_fixture(tmp_path)
    phone = tmp_path / "phone"
    phone.mkdir()
    devices = DeviceManager(tmp_path, MountedVolumes({"phone": str(phone)}))
    service = AppCatalog(tmp_path, devices)

    def fetch(source, item):
        key = item["name"].removesuffix(".jar")
        raw = jar_bytes(key)
        directory = service.root / "cache" / item["sha256"]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / item["name"]
        path.write_bytes(raw)
        return path, dict(item, validation=validate_package(path.name, raw), cache_hit=False)

    service.downloader.fetch = fetch
    request = {
        "action": "transfer",
        "ids": ["example"],
        "device": "phone",
        "path": "",
        "confirm": True,
    }
    job = wait_job(service, service.execute(request)["id"])
    assert job["state"] == "completed"
    assert [i["id"] for i in job["items"]] == ["runtime", "example"]
    assert all(i["stage"] == "awaiting-installation" for i in job["items"])
    assert all(i["integrity"] == "sha256-read-back" for i in job["items"])
    repeat = wait_job(service, service.execute(request)["id"])
    assert repeat["state"] == "completed"  # Existing identical files are not overwritten.
    confirmed = service.execute(
        {"action": "confirm-installed", "job": job["id"], "app": "example", "confirm": True}
    )
    assert confirmed["items"][-1]["stage"] == "user-confirmed-installed"
    assert confirmed["items"][-1]["evidence"] == "manual user observation"
    service.execute({"action": "save-set", "name": "My phone", "ids": ["example"]})
    assert AppCatalog(tmp_path, devices).state()["sets"]["My phone"] == ["example"]
    with pytest.raises(ValueError):
        service.execute(dict(request, ids=["manual"]))


def test_failed_dependency_is_not_transferred_and_restart_is_honest(tmp_path):
    catalog_fixture(tmp_path)
    service = AppCatalog(tmp_path, DeviceManager(tmp_path))
    service.downloader.fetch = lambda *args: (_ for _ in ()).throw(ValueError("unavailable"))
    job = wait_job(service, service.execute({"action": "download", "ids": ["example"]})["id"])
    assert all(i["stage"] == "failed" for i in job["items"])
    assert "Dependency failed" in job["items"][-1]["error"]
    job["state"] = "running"
    job["items"][0]["stage"] = "downloading"
    path = service.root / "jobs" / (job["id"] + ".json")
    path.write_text(json.dumps(job))
    restored = AppCatalog(tmp_path, service.devices).job(job["id"])
    assert restored["state"] == "interrupted" and restored["items"][0]["stage"] == "interrupted"


def test_catalog_http_requires_session_and_rejects_url_injection(http_server):  # noqa: F811
    state, port = http_server
    payload = {"action": "list"}
    assert _http(port, "POST", "/api/catalog", payload)[0] == 403
    headers = {"X-Symport-Token": state.token}
    status, body = _http(port, "POST", "/api/catalog", payload, headers)
    assert status == 200 and len(json.loads(body)["apps"]) >= 30
    assert (
        _http(
            port,
            "POST",
            "/api/catalog",
            {"action": "download", "ids": ["https://localhost/private"]},
            headers,
        )[0]
        == 400
    )


def test_real_sis_compression_uses_uncompressed_length_for_hash_check(monkeypatch):
    import zlib

    from symport.sis import fields, reader, writer

    content = b"Symbian compressed payload " * 200
    original_u64 = fields.u64
    first = True

    def description_length(value):
        nonlocal first
        if first:
            first = False
            return original_u64(len(zlib.compress(content)))
        return original_u64(value)

    def compressed(data):
        return fields.field(
            fields.T_COMPRESSED, fields.u32(1) + original_u64(len(data)) + zlib.compress(data)
        )

    monkeypatch.setattr(fields, "u64", description_length)
    monkeypatch.setattr(fields, "compressed_raw", compressed)
    package = writer.SisPackage(
        0xE0001234, "Compressed", "Test", (1, 0, 0), [writer.SisFile("!:\\data\\test.txt", content)]
    )
    info = reader.inspect(writer.build(package))
    entry = info["files"][0]
    assert entry["length"] != entry["uncompressed_length"]
    assert entry["actual_length"] == entry["uncompressed_length"] and entry["hash_ok"]


def test_sis_declared_decompression_limit():
    from symport.sis import fields, reader

    with pytest.raises(ValueError, match="128 MiB"):
        reader._decompress(fields.u32(1) + fields.u64(129 * 1024 * 1024) + b"compressed")


def test_sis_null_operation_does_not_hash_or_extract_data_slot_zero(monkeypatch):
    from symport.sis import fields, reader, writer

    original_field = fields.field

    def null_description(kind, payload=b"", in_array=False):
        if kind == fields.T_FILE_DESCRIPTION:
            cursor = fields.Cursor(payload)
            _, target, _ = cursor.field(fields.T_STRING)
            _, mime, _ = cursor.field(fields.T_STRING)
            payload = (
                fields.field(fields.T_STRING, target)
                + fields.field(fields.T_STRING, mime)
                + fields.field(fields.T_HASH, fields.u32(1) + fields.field(fields.T_BLOB, b""))
                + fields.u32(8)
                + fields.u32(0)
                + fields.u64(0)
                + fields.u64(0)
                + fields.u32(0)
            )
        return original_field(kind, payload, in_array=in_array)

    monkeypatch.setattr(fields, "field", null_description)
    package = writer.SisPackage(
        0xE0001234,
        "Null entry",
        "Test",
        (1, 0, 0),
        [writer.SisFile("!:\\data\\settings.ini", b"not settings")],
    )
    raw = writer.build(package)
    assert reader.inspect(raw)["files"][0]["hash_ok"] is None
    assert reader.extract(raw) == {}


def test_conflicting_filenames_are_detected_before_transfer(tmp_path):
    catalog_fixture(tmp_path)
    catalog = Catalog(tmp_path / "catalog")
    catalog.sources["example"]["artifacts"][0]["name"] = "runtime.jar"
    assert any("Conflicting package filename" in p for p in catalog.plan(["example"])["problems"])


def test_insufficient_space_never_starts_network_or_writes(tmp_path):
    catalog_fixture(tmp_path)

    class NoSpace:
        def devices(self):
            return [{"id": "phone", "connected": True, "capabilities": ["files"], "free": 0}]

        def execute(self, data):
            pytest.fail("Phone writes must not start")

    service = AppCatalog(tmp_path, DeviceManager(tmp_path, NoSpace()))
    service.downloader.fetch = lambda *args: pytest.fail("Network must not start")
    key = service.execute(
        {"action": "transfer", "ids": ["example"], "device": "phone", "confirm": True}
    )["id"]
    job = wait_job(service, key)
    assert job["state"] == "failed" and "free space" in job["error"]
    assert all(i["stage"] == "failed" for i in job["items"])
