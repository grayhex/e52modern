"""Regression tests on artifacts produced by the real symbian-platform 0.3.0 SDK.

Fixtures (tests/fixtures, see README there): an ARMv5T E32 executable built by the SDK from its
own `probes/e32_probe`, the SIS the SDK's writer made from it, a signed copy, and the SDK's own
inspector output for each. They anchor SymPort's parsers to an independent implementation.
"""
import json
import os
import subprocess
import sys

from symport.analysis import crosscheck, e32
from symport.sis import reader, writer
from tests.helpers import REPO, write_tool

FIX = REPO / "tests" / "fixtures"


def load(name):
    return (FIX / name).read_bytes()


def sdk_json(name):
    return json.loads((FIX / name).read_text())["result"]["metadata"]


def test_e32_header_matches_sdk_inspector_field_by_field():
    raw = load("e32_probe_armv5t.exe")
    rows = crosscheck.compare(e32.analyze(raw), raw, sdk_json("e32_probe_armv5t.sdk-inspect.json"))
    bad = [(k, a, b) for k, a, b, ok in rows if not ok]
    assert bad == []
    assert len(rows) >= 14


def test_real_image_facts():
    info = e32.analyze(load("e32_probe_armv5t.exe"))
    assert (info["kernel"], info["cpu"], info["abi"], info["header_format"]) == ("eka2", "armv5", "eabi", "V")
    assert info["uid_checksum_ok"] and info["header_crc_ok"] and info["imports"] == []


def test_sis_reader_matches_sdk_inspector():
    meta = sdk_json("sdk_probe_package.sdk-inspect.json")
    info = reader.inspect(load("sdk_probe_package.sis"))
    assert info["uid_checksum_ok"] and info["controller_crc_ok"] and info["data_crc_ok"]
    assert info["package"]["uid"] == meta["uid"]
    assert info["package"]["names"] == [meta["name"]]
    assert info["package"]["vendor_names"] == [meta["vendor"]]
    assert info["package"]["version"] == meta["version"]
    assert [f["target"] for f in info["files"]] == [meta["target"]]
    assert info["files"][0]["sha1"] == meta["files"][0]["sha1"] == meta["executable_sha1"]
    assert info["files"][0]["hash_ok"] is True and info["signed"] is False


def test_embedded_e32_extracted_from_real_sis_is_the_original_image():
    blobs = reader.extract(load("sdk_probe_package.sis"))
    assert blobs["!:\\sys\\bin\\probe.exe"] == load("e32_probe_armv5t.exe")


def test_native_writer_is_byte_identical_to_sdk_writer():
    """Strongest format check available without MakeSIS: same input -> same bytes as the SDK."""
    pkg = writer.SisPackage(0xE0000809, "Symbian E32 Probe", "Symbian research", (1, 0, 0),
                            [writer.SisFile("!:\\sys\\bin\\probe.exe", load("e32_probe_armv5t.exe"))])
    assert writer.build(pkg) == load("sdk_probe_package.sis")


def test_signed_sdk_package_is_recognised_as_signed():
    info = reader.inspect(load("sdk_probe_package_signed.sis"))
    assert info["signed"] is True and info["signature_count"] == 1
    assert info["controller_crc_ok"] and info["data_crc_ok"] and info["files"][0]["hash_ok"]
    assert info["package"]["uid"] == reader.inspect(load("sdk_probe_package.sis"))["package"]["uid"]


def test_crosscheck_cli_with_fake_sdk_replaying_real_output(tmp_path):
    """`--cross-check` agrees when the (fake) SDK replays the real inspector JSON, and flags a lie."""
    golden = (FIX / "e32_probe_armv5t.sdk-inspect.json").read_text()
    fake = write_tool(tmp_path / "symbian", f"import sys; sys.stdout.write({golden!r})")
    env = dict(os.environ, SYMPORT_SYMBIAN=str(fake), PYTHONPATH=str(REPO))
    cmd = [sys.executable, "-m", "symport", "app", "inspect", str(FIX / "e32_probe_armv5t.exe"),
           "--cross-check", "--json"]
    d = json.loads(subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, env=env).stdout)
    cc = next(c for c in d["checks"] if c["id"] == "crosscheck.e32")
    assert cc["status"] == "pass" and "agree" in cc["message"]
    lie = json.loads(golden)
    lie["result"]["metadata"]["code_size"] = 999
    fake = write_tool(tmp_path / "symbian2", f"import sys; sys.stdout.write({json.dumps(lie)!r})")
    env["SYMPORT_SYMBIAN"] = str(fake)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, env=env)
    cc = next(c for c in json.loads(r.stdout)["checks"] if c["id"] == "crosscheck.e32")
    assert cc["status"] == "fail" and "code_size" in cc["message"] and r.returncode == 1


def test_crosscheck_skipped_without_sdk():
    env = dict(os.environ, PYTHONPATH=str(REPO), PATH="/usr/bin:/bin")
    env.pop("SYMPORT_SYMBIAN", None)
    cmd = [sys.executable, "-m", "symport", "app", "inspect", str(FIX / "e32_probe_armv5t.exe"),
           "--cross-check", "--json"]
    d = json.loads(subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, env=env).stdout)
    assert next(c for c in d["checks"] if c["id"] == "crosscheck.e32")["status"] == "skip"


def test_summarize_and_known_hints():
    from symport.backends import modern_sdk
    from symport.util import RunResult
    r = RunResult(["symbian"], 1, '{"status": {"name": "FAILED_PRECONDITION", "message": "SDK input tracking '
                  'requires Ninja 1.12 or later"}}', "")
    msg = modern_sdk.summarize(r, json.loads(r.stdout))
    assert "FAILED_PRECONDITION" in msg and "NEXT TO the compiler" in msg
    assert "standalone `symbian-native`" in modern_sdk.summarize(
        RunResult(["symbian"], 1, "", "needs the standalone symbian-native tool: /bin/symbian-native"), None)


def test_sis_compare_semantics():
    from symport.sis import compare
    plain, signed = load("sdk_probe_package.sis"), load("sdk_probe_package_signed.sis")
    assert compare.compare(plain, plain) == []
    d = compare.compare(plain, signed)
    assert [x["field"] for x in d] == ["signed"]            # same installer content, only the signature differs
    other = writer.build(writer.SisPackage(0xE0000809, "Symbian E32 Probe", "Symbian research", (1, 0, 0),
                                           [writer.SisFile("!:\\sys\\bin\\probe.exe", b"different")]))
    assert any(x["field"].startswith("file ") for x in compare.compare(plain, other))


def test_sis_compare_cli(tmp_path):
    cmd = [sys.executable, "-m", "symport", "sis", "compare", str(FIX / "sdk_probe_package.sis"),
           str(FIX / "sdk_probe_package_signed.sis"), "--json"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, env=dict(os.environ, PYTHONPATH=str(REPO)))
    d = json.loads(r.stdout)
    assert r.returncode == 1 and d["data"]["differences"][0]["field"] == "signed"
