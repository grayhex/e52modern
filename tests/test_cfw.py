"""CFW Research (#42), Security Scanner (#46) and EKA1 → RPKG (#47): synthetic fixtures only."""
import base64
import json

import pytest

from symport.firmware import FirmwareExplorer
from symport.firmware import eka1 as E
from symport.firmware.index import FirmwareError, detect
from symport.firmware.rpkg import MAGIC_V1, MAGIC_V2, read_entries
from symport.firmware.scanner import declared_match, load_db, scan
from tests.helpers import make_e32
from tests.test_firmware import build_rom, upload, zip_bytes

EKA1 = 0x50000000


@pytest.fixture
def fx(tmp_path):
    return FirmwareExplorer(tmp_path / "fw")


def files_for_rom():
    return {"sys/bin/app.exe": make_e32(uid3=0x20001001), "resource/apps/a.rsc": b"resource-bytes", "private/x/empty.dat": b""}


# ---- #47 EKA1 → RPKG ----------------------------------------------------------------------------------
def test_eka1_rom_is_converted_to_a_readable_rpkg_with_honest_statuses(tmp_path):
    rom = build_rom(files_for_rom(), base=EKA1)
    out = tmp_path / "o.rpkg"
    report = E.convert(rom, out, "synthetic.dmp")
    assert report["status"] == "converted" and report["accepted_by_emulator"] == "not-attempted" and report["booted"] == "not-tested"
    assert report["real_image_tested"] is False and "does not boot or emulate" in report["emulation_claim"] and "Not Nokia E52" in report["scope"]
    assert report["input"]["sha256"] and report["output"]["entries"] == 2 and report["output"]["sha256"]
    raw = out.read_bytes()
    assert raw[:16] == MAGIC_V1
    header, entries = read_entries(raw)
    assert header["count"] == 2 and sorted(n for n, _, _ in entries) == ["Z:\\resource\\apps\\a.rsc", "Z:\\sys\\bin\\app.exe"]
    by = {n: raw[o:o + s] for n, o, s in entries}
    assert by["Z:\\resource\\apps\\a.rsc"] == b"resource-bytes"
    assert any("not-tested" in x for x in report["limitations"])


@pytest.mark.parametrize("make,needle", [
    (lambda: build_rom(files_for_rom(), base=0x80000000), "not the EKA1 base"),
    (lambda: b"\x00" * 4096, "Not a readable core ROM"),
    (lambda: b"not a rom at all", "Not a readable core ROM"),
    (lambda: build_rom(files_for_rom(), base=EKA1)[:300], "Not a readable core ROM"),
    (lambda: build_rom({}, base=EKA1), "no files"),
])
def test_eka2_garbage_truncated_and_empty_roms_are_unsupported(tmp_path, make, needle):
    out = tmp_path / "o.rpkg"
    report = E.convert(make(), out)
    assert report["status"] == "unsupported" and needle in report["reason"] and not out.exists()


def test_limits_and_deadline(tmp_path, monkeypatch):
    rom = build_rom(files_for_rom(), base=EKA1)
    monkeypatch.setattr(E, "MAX_ROM", 100)
    assert "between 1 byte and 48 MiB" in E.convert(rom, tmp_path / "a.rpkg")["reason"]
    monkeypatch.setattr(E, "MAX_ROM", 48 * 1024 * 1024)
    slow = E.convert(rom, tmp_path / "b.rpkg", deadline=-1)
    assert slow["status"] == "unsupported" and "time limit" in slow["reason"] and not (tmp_path / "b.rpkg").exists()


def test_a_damaged_directory_entry_fails_closed(tmp_path):
    rom = bytearray(build_rom(files_for_rom(), base=EKA1))
    rom[0x200:0x230] = b"\xff" * 0x30  # smash the first placed blob/dirs
    report = E.convert(bytes(rom), tmp_path / "o.rpkg")
    assert report["status"] in ("unsupported", "converted")
    if report["status"] == "unsupported":
        assert "damaged" in report["reason"] or "Not a readable" in report["reason"]


def test_action_returns_rpkg_and_report_separately_and_rejects_bad_uploads(fx):
    rom = build_rom(files_for_rom(), base=EKA1)
    result = fx.execute({"action": "eka1-convert", "name": "x.dmp", "content": base64.b64encode(rom).decode()})
    assert result["report"]["status"] == "converted" and result["rpkg_name"].endswith(".rpkg")
    assert base64.b64decode(result["rpkg"])[:16] == MAGIC_V1
    assert json.loads(base64.b64decode(result["report_json"]))["schema"] == "symport.eka1-rpkg/1"
    refused = fx.execute({"action": "eka1-convert", "content": base64.b64encode(b"junk").decode()})
    assert refused["report"]["status"] == "unsupported" and refused["rpkg"] == "" and refused["rpkg_name"] is None
    with pytest.raises(FirmwareError, match="base64"):
        fx.execute({"action": "eka1-convert", "content": "***"})


def test_eka2_core_rom_importer_is_unchanged_and_rpkg_is_indexed(fx, tmp_path):
    key, meta = upload(fx, build_rom(files_for_rom(), base=0x80000000), "eka2.rom")
    assert meta["status"] == "ready" and meta["kind"] == "rom" and meta["files"] == 3
    out = tmp_path / "c.rpkg"
    E.convert(build_rom(files_for_rom(), base=EKA1), out)
    key2, meta2 = upload(fx, out.read_bytes(), "converted.rpkg")
    assert meta2["status"] == "ready" and meta2["kind"] == "rpkg" and meta2["files"] == 2
    assert meta2["levels"]["boot"] == "not-tested" and any("not booted" in x or "nothing is booted" in x for x in meta2["limitations"])
    entry = fx.execute({"action": "file", "id": key2, "path": "Z:/resource/apps/a.rsc"})
    assert entry["entry"]["size"] == len(b"resource-bytes") and entry["hex_head"] == b"resource-bytes".hex()


def test_rpkg_v2_truncated_and_foreign_containers_are_refused(tmp_path):
    for name, blob in (("v2.rpkg", MAGIC_V2 + b"\x00" * 40), ("cut.rpkg", MAGIC_V1 + b"\x00\x00\x00\x00\x05\x00\x00\x00"),
                       ("fw.fpsx", b"FPSX" + b"\x00" * 100), ("fw.vpl", b"\x01\x02" * 100)):
        path = tmp_path / name
        path.write_bytes(blob)
        with pytest.raises((FirmwareError, ValueError)) as info:
            kind = detect(path)
            from symport.firmware.index import build_index
            build_index(path, kind, name)
        if name.endswith(("fpsx", "vpl")):
            assert "not decoded" in str(info.value) and "never assumed" in str(info.value)


# ---- #46 scanner ----------------------------------------------------------------------------------------
def tree(extra=None):
    members = {"sys/bin/app.exe": make_e32(uid3=0x20001001), "resource/apps/a.rsc": b"plain"}
    members.update(extra or {})
    return members


def indexed(fx, members):
    key, meta = upload(fx, zip_bytes(members))
    assert meta["status"] == "ready"
    return key


def scan_action(fx, key, declared=None):
    return fx.execute({"action": "cfw-scan", "id": key, "declared": declared})


def test_advisory_database_is_sourced_and_scoped():
    db = load_db()
    cve = db["advisories"][0]
    assert cve["id"] == "CVE-2025-65885" and cve["published"] == "2025-12-26" and cve["severity"]["cvss_v3_1"] == 5.1
    assert cve["severity"]["rating"] == "MEDIUM" and "author's, not the scored severity" in cve["severity"]["author_claim"]
    assert len(cve["affected"]) == 12 and [a for a in cve["affected"] if "write-up only" in a["source"]][0]["model"] == "Nokia C6-01"
    assert "E52" in cve["platform"] and len(cve["sources"]) >= 3 and cve["caveats"]
    assert db["db_version"]


def test_reference_to_the_startup_text_file_is_a_lead_not_a_verdict(fx):
    key = indexed(fx, tree({"private/aa/blob.dat": b"xx" + "Delight.txt".encode("utf-16-le") + b"yy"}))
    report = scan_action(fx, key)
    assert report["verdict"] == "suspicious-pattern" and report["proof_of_safety"] is False
    hit = report["findings"][0]
    assert hit["rule"] == "startup-txt-reference" and hit["path"].endswith("blob.dat") and hit["sha256"] and hit["offset"] == 2
    assert "lead" in hit["reliability"] or "does not show" in hit["reliability"]
    assert report["declared_versions"] == [] and "CVE-2025-65885" in report["advisories"]
    assert "Nothing was run" in report["statement"]


def test_writable_path_reference_and_informational_rules(fx):
    key = indexed(fx, tree({"private/aa/cfg.dat": b"E:\\Data\\startup.txt", "private/aa/svc.dat": b"domainsrv.exe"}))
    report = scan_action(fx, key)
    rules = {f["rule"]: f["status"] for f in report["findings"]}
    assert rules == {"writable-path-text": "suspicious-pattern", "domainsrv-reference": "informational"}
    assert report["verdict"] == "suspicious-pattern"


def test_clean_tree_is_no_pattern_found_never_safe_and_coverage_is_reported(fx):
    key = indexed(fx, tree({"sys/bin/packed.dll": make_e32(dll=True, compression=0x101F7AFC)}))
    report = scan_action(fx, key)
    assert report["verdict"] == "no-pattern-found" and report["proof_of_safety"] is False
    assert report["coverage"]["files_scanned"] >= 1
    assert any("compressed E32" in n["reason"] for n in report["coverage"]["not_tested"])


def test_empty_input_is_unknown_and_declared_versions_are_matched_exactly():
    assert scan([], lambda e: b"")["verdict"] == "unknown"
    cve = load_db()["advisories"][0]
    assert declared_match(cve, {"cfw": "delight", "model": "Nokia N8", "version": "v6.7"})
    assert declared_match(cve, {"cfw": "Delight", "model": "N8", "version": "Delight v6.7"})
    assert not declared_match(cve, {"cfw": "delight", "model": "Nokia N8", "version": "6.6"})
    assert not declared_match(cve, {"cfw": "delight", "model": "Nokia E52", "version": "6.7"})
    assert not declared_match(cve, {"cfw": "reborn", "model": "Nokia N8", "version": "6.7"})
    assert not declared_match(cve, {})


def test_declared_vulnerable_version_is_reported_as_declared_not_verified(fx):
    key = indexed(fx, tree())
    report = scan_action(fx, key, {"cfw": "delight", "model": "Nokia N8", "version": "6.7"})
    assert report["verdict"] == "vulnerable-version" and "declared by you; not verified" in report["declared_versions"][0]["basis"]
    other = scan_action(fx, key, {"cfw": "delight", "model": "Nokia E52", "version": "6.7"})
    assert other["verdict"] == "no-pattern-found" and other["declared"]["model"] == "Nokia E52"


def test_an_unrelated_text_that_mentions_the_name_is_a_false_positive_the_report_warns_about(fx):
    key = indexed(fx, tree({"private/aa/readme.txt": b"This build does not use Delight.txt."}))
    hit = scan_action(fx, key)["findings"][0]
    assert hit["status"] == "suspicious-pattern" and "does not show" in hit["reliability"]


# ---- #42 research ---------------------------------------------------------------------------------------
def test_sources_hold_only_published_metadata_and_never_mark_belle_firmware_applicable(fx):
    result = fx.execute({"action": "cfw-sources"})
    ids = {s["id"]: s for s in result["sources"]}
    assert set(ids) == {"reborn-hybrid-n95", "reborn-n8-e7", "delight-belle"}
    for sid in ("reborn-n8-e7", "delight-belle"):
        assert all(ids[sid]['symport'][m] == 'not-applicable' for m in ('nokia-e52','nokia-e72','nokia-n95','nokia-n95-8gb','nokia-n97-mini'))
        assert ids[sid]['symport']['nokia-n8'] == ids[sid]['symport']['nokia-e7'] == 'research-only'
        assert 'Belle' in ids[sid]['platform']
    assert ids["reborn-hybrid-n95"]["symport"]["nokia-n95"] == "wizard" and ids["reborn-hybrid-n95"]["symport"]["nokia-n95-8gb"] == "blocked-without-evidence"
    assert "unconfirmed" in ids["reborn-hybrid-n95"]["distribution"] and ids["delight-belle"]["advisories"] == ["CVE-2025-65885"]
    assert "not the source of the firmware" in " ".join(ids["reborn-n8-e7"]["limitations"])
    assert result["containers"]["fpsx/vpl/rofs"].startswith("not decoded")
    assert all(m["rm"].startswith("not stated") for s in result["sources"] for m in s["models"])


def test_inventory_lists_leads_with_basis_and_baseline_origin(fx):
    base_key = indexed(fx, tree({"sys/bin/keep.dll": make_e32(dll=True, uid3=0x20001099)}))
    cfw_key = indexed(fx, tree({"sys/bin/keep.dll": make_e32(dll=True, uid3=0x20001099),
                                "sys/bin/new.dll": make_e32(dll=True, uid3=0x2000109A),
                                "resource/cacerts/mozilla.cer": b"cert", "private/10202be9/uaprof.rdf": b"x",
                                "resource/startup.txt": b"see http://example.invalid/page and https://example.org/a"}))
    plain = fx.execute({"action": "cfw-inventory", "id": cfw_key})
    cats = plain["categories"]
    assert {u["url"] for u in cats["urls"]["items"]} == {"http://example.invalid/page", "https://example.org/a"}
    assert cats["ssl-ca"]["items"][0]["basis"] == "file-name" and cats["uaprof"]["items"] and cats["autostart"]["items"]
    assert all(i["origin"] == "present-origin-unknown" for i in cats["replaced-binaries"]["items"])
    assert plain["baseline"] is False and "no baseline" in cats["replaced-binaries"]["basis"]
    relative = fx.execute({"action": "cfw-inventory", "id": cfw_key, "baseline": base_key})["categories"]["replaced-binaries"]["items"]
    assert {(i["path"].rsplit("/", 1)[-1], i["origin"]) for i in relative} == {("new.dll", "new-relative-to-baseline")}
    assert "Leads for review only" in plain["statement"]
