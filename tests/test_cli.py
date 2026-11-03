"""CLI smoke tests (subprocess, JSON output) - no phone, no proprietary SDK."""
import json
import subprocess
import sys

import pytest

from symport.report import SCHEMA
from tests.helpers import REPO, make_e32, write_tool


def sp(*args, env=None, check=None):
    import os
    e = dict(os.environ)
    e.update(env or {})
    e["PYTHONPATH"] = str(REPO)
    r = subprocess.run([sys.executable, "-m", "symport", *args], capture_output=True, text=True, cwd=REPO, env=e)
    if check is not None:
        assert r.returncode == check, r.stdout + r.stderr
    return r


def js(r):
    return json.loads(r.stdout)


def test_version_and_help():
    r = sp("--version", check=0)
    assert "symport" in r.stdout
    assert "doctor" in sp("--help", check=0).stdout


def test_doctor_json_schema_and_optional_tools_do_not_block():
    r = sp("doctor", "--json", check=0)
    d = js(r)
    assert d["schema"] == SCHEMA and d["command"] == "doctor" and d["status"] == "ok"
    names = {t["name"] for t in d["data"]["tools"]}
    assert {"skc", "bmconv", "mifbuild", "s60inspect", "makesis", "signsis", "symbian", "eka2l1"} <= names
    assert d["data"]["readiness"]["theme package (native, experimental)"] is True
    assert d["data"]["profiles"][0]["id"] == "nokia-e52"


def test_doctor_detects_fake_tools(tmp_path):
    mk = write_tool(tmp_path / "makesis", "pass")
    r = sp("doctor", "--json", env={"SYMPORT_MAKESIS": str(mk)}, check=0)
    t = {x["name"]: x for x in js(r)["data"]["tools"]}
    assert t["makesis"]["found"] is True and t["signsis"]["found"] is False


def test_profile_commands():
    d = js(sp("profile", "list", "--json", check=0))
    assert d["data"]["profiles"][0]["id"] == "nokia-e52"
    d = js(sp("profile", "show", "nokia-e52", "--json", check=0))
    assert d["data"]["profile"]["facts"]["firmware.version"]["status"] == "unknown"
    r = sp("profile", "show", "nokia-n8", "--json")
    assert r.returncode == 2 and "unknown device profile" in r.stdout


def test_theme_inspect_json_both_variants():
    r = sp("theme", "inspect", "--json", check=0)
    d = js(r)
    assert d["status"] == "ok" and d["verification"]["physical_device"] == "not-tested"
    assert any(c["id"] == "light.mbm.structure" and c["status"] == "pass" for c in d["checks"])
    assert any(c["id"] == "dark.device.install" and c["status"] == "unknown" for c in d["checks"])


def test_theme_inspect_report_file(tmp_path):
    out = tmp_path / "r.json"
    sp("theme", "inspect", "--variant", "light", "--report", str(out), check=0)
    assert json.loads(out.read_text())["command"] == "theme inspect"


def test_theme_package_without_makesis_is_unsupported_not_success():
    r = sp("theme", "package", "--variant", "light", "--json")
    d = js(r)
    assert r.returncode == 3 and d["status"] == "unsupported"
    assert d["artifacts"] == [] and any("SYMPORT_MAKESIS" in i for i in d["data"]["instructions"])


def test_theme_package_modern_sdk_backend_cannot_package_themes():
    r = sp("theme", "package", "--variant", "dark", "--backend", "modern-sdk", "--json")
    d = js(r)
    assert r.returncode == 3 and "executables only" in d["data"]["unsupported_reason"]


def test_theme_package_native_is_labelled_experimental(tmp_path):
    r = sp("theme", "package", "--variant", "dark", "--backend", "native", "--output", str(tmp_path), "--json", check=0)
    d = js(r)
    assert d["status"] == "ok" and any("EXPERIMENTAL" in x for x in d["limitations"])
    assert any(c["id"] == "sis.contents" and c["status"] == "pass" for c in d["checks"])
    assert any(c["id"] == "device.install" and c["status"] == "unknown" for c in d["checks"])
    sis = tmp_path / "e52cleardark.sis"
    assert sis.is_file()
    # round-trip through the standalone inspector
    r2 = sp("sis", "inspect", str(sis), "--json", check=0)
    d2 = js(r2)
    assert d2["data"]["compatibility"]["status"] == "not-tested"     # resource-only package
    assert any(c["id"] == "sis.signature" and c["status"] == "warn" for c in d2["checks"])


def test_theme_package_with_fake_makesis_and_signsis(tmp_path):
    # Fake "official" tools: makesis copies a native SIS; signsis copies input to output.
    native = tmp_path / "native.sis"
    sp("theme", "package", "--variant", "light", "--backend", "native", "--output", str(tmp_path / "n"), check=0)
    native.write_bytes((tmp_path / "n" / "e52clearlight.sis").read_bytes())
    mk = write_tool(tmp_path / "makesis",
                    f"import sys, shutil; assert sys.argv[1].endswith('.pkg'); shutil.copy({str(native)!r}, sys.argv[2])")
    sg = write_tool(tmp_path / "signsis", "import sys, shutil; shutil.copy(sys.argv[1], sys.argv[2])")
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("x"), key.write_text("y")
    r = sp("theme", "package", "--variant", "light", "--output", str(tmp_path / "o"), "--cert", str(cert),
           "--key", str(key), "--json", env={"SYMPORT_MAKESIS": str(mk), "SYMPORT_SIGNSIS": str(sg)}, check=0)
    d = js(r)
    ids = {c["id"]: c for c in d["checks"]}
    assert ids["makesis.run"]["status"] == "pass" and ids["sign.run"]["status"] == "pass"
    assert d["data"]["package"]["backend"] == "makesis"
    assert (tmp_path / "o" / "e52clearlight.sisx").is_file()


def test_theme_package_makesis_failure_is_reported(tmp_path):
    mk = write_tool(tmp_path / "makesis", "import sys; sys.stderr.write('boom'); sys.exit(2)")
    r = sp("theme", "package", "--variant", "light", "--output", str(tmp_path), "--json",
           env={"SYMPORT_MAKESIS": str(mk)})
    d = js(r)
    assert r.returncode == 1 and d["status"] == "failed" and d["artifacts"] == []


def test_makesis_producing_no_file_is_not_success(tmp_path):
    mk = write_tool(tmp_path / "makesis", "pass")      # exits 0 but writes nothing
    r = sp("theme", "package", "--variant", "light", "--output", str(tmp_path), "--json",
           env={"SYMPORT_MAKESIS": str(mk)})
    assert r.returncode == 1 and js(r)["artifacts"] == []


def test_makesis_producing_garbage_is_rejected(tmp_path):
    mk = write_tool(tmp_path / "makesis", "import sys; open(sys.argv[2],'wb').write(b'not a sis file at all')")
    r = sp("theme", "package", "--variant", "light", "--output", str(tmp_path), "--json",
           env={"SYMPORT_MAKESIS": str(mk)})
    d = js(r)
    assert r.returncode == 1 and any(c["id"] == "sis.parse" and c["status"] == "fail" for c in d["checks"])


def test_missing_repo_gives_usage_error_json(tmp_path):
    r = sp("theme", "inspect", "--repo", str(tmp_path), "--json")
    assert r.returncode == 2 and "not an E52Modern checkout" in js(r)["error"]


@pytest.mark.parametrize("args", [
    ("app", "init", "--name", "hello", "--dest", "{tmp}/hello"),
    ("device", "list"),
    ("device", "info"),
])
def test_missing_modern_sdk_gives_diagnostics(args, tmp_path):
    args = [a.format(tmp=tmp_path) for a in args]
    r = sp(*args, "--json")
    d = js(r)
    assert r.returncode == 3 and d["status"] == "unsupported"
    assert any("pip install symbian-platform" in i for i in d["data"]["instructions"])


def test_app_analyze_file(tmp_path):
    exe = tmp_path / "a.exe"
    exe.write_bytes(make_e32(imports={"euser[100039e5].dll": [1]}))
    d = js(sp("app", "analyze", str(exe), "--json", check=0))
    assert d["data"]["compatibility"]["status"] == "unknown" and d["data"]["compatibility"]["runtime"] == "not-tested"
    fw = tmp_path / "fw.json"
    fw.write_text('{"schema":1,"id":"mine","device":"nokia-e52","source":"my dump","dlls":{"euser.dll":{"ordinals":[1]}}}')
    d = js(sp("app", "analyze", str(exe), "--firmware-profile", str(fw), "--json", check=0))
    assert d["data"]["compatibility"]["status"] == "compatible"
    bad = tmp_path / "bad.exe"
    bad.write_bytes(b"MZ" + b"\0" * 100)
    r = sp("app", "analyze", str(bad), "--json")
    assert r.returncode == 1 and js(r)["status"] == "failed"


def test_report_matrix(tmp_path):
    sp("theme", "inspect", "--variant", "light", "--report", str(tmp_path / "a.json"), check=0)
    exe = tmp_path / "a.exe"
    exe.write_bytes(make_e32())
    sp("app", "analyze", str(exe), "--report", str(tmp_path / "b.json"), check=0)
    d = js(sp("report", "matrix", str(tmp_path), "--json", check=0))
    assert len(d["data"]["rows"]) == 2
    assert all(r["physical_device"] == "not-tested" for r in d["data"]["rows"])
