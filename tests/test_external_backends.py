"""Fake symbian CLI / EKA2L1 to exercise delegation and honest reporting."""
import json
import subprocess
import sys

from symport.sis import writer
from tests.helpers import REPO, make_e32, write_tool


def sp(*args, env=None):
    import os
    e = dict(os.environ)
    e.update(env or {})
    e["PYTHONPATH"] = str(REPO)
    return subprocess.run([sys.executable, "-m", "symport", *args], capture_output=True, text=True, cwd=REPO, env=e)


def sis_file(tmp_path, name="t.sis"):
    p = tmp_path / name
    p.write_bytes(writer.build(writer.SisPackage(0xE0000001, "T", "v", (1, 0, 0),
                                                 [writer.SisFile("!:\\sys\\bin\\t.exe", make_e32())])))
    return p


FAKE_SYMBIAN = r"""
import sys, json
a = sys.argv[1:]
open(sys.argv[0] + '.calls', 'a').write(json.dumps(a) + '\n')
if a[:2] == ['device', 'list']:
    print('0: Nokia (usb) mass-storage')
elif a[:2] == ['device', 'info']:
    print('serial not printed')
elif a[:2] == ['device', 'install']:
    print('staged; awaiting-on-device-install')
elif a[:1] == ['--version']:
    print('symbian 0.3.0')
else:
    sys.exit(0)
"""


def test_device_list_info_stage_delegate_and_never_claim_install(tmp_path):
    fake = write_tool(tmp_path / "symbian", FAKE_SYMBIAN)
    env = {"SYMPORT_SYMBIAN": str(fake)}
    d = json.loads(sp("device", "list", "--json", env=env).stdout)
    assert d["status"] == "ok" and "mass-storage" in d["data"]["output"]
    sis = sis_file(tmp_path)
    r = sp("device", "stage", str(sis), "--device", "0", "--json", env=env)
    d = json.loads(r.stdout)
    assert r.returncode == 0
    assert d["verification"]["physical_device"] == "staged-not-installed"
    inst = next(c for c in d["checks"] if c["id"] == "device.install")
    assert inst["status"] == "unknown" and inst["level"] == "device"
    calls = [json.loads(line) for line in open(str(fake) + ".calls")]
    assert ["device", "install", "--package", str(sis), "--device", "0"] in calls
    # no destructive / firmware verbs are ever issued
    assert not any(x in " ".join(c) for c in calls for x in ("flash", "erase", "format", "recovery"))


def test_device_stage_refuses_garbage(tmp_path):
    fake = write_tool(tmp_path / "symbian", FAKE_SYMBIAN)
    junk = tmp_path / "x.sis"
    junk.write_bytes(b"hello")
    r = sp("device", "stage", str(junk), "--json", env={"SYMPORT_SYMBIAN": str(fake)})
    assert r.returncode == 1
    assert not (tmp_path / "symbian.calls").exists()


def test_emulator_list_without_config(tmp_path):
    d = json.loads(sp("emulator", "list", "--json").stdout)
    assert d["data"]["eka2l1"]["path"] is None
    assert any(c["id"] == "config.command" and c["status"] == "warn" for c in d["checks"])


def test_emulator_test_requires_configured_command(tmp_path):
    sis = sis_file(tmp_path)
    r = sp("emulator", "test", str(sis), "--json")
    d = json.loads(r.stdout)
    assert r.returncode == 3 and d["status"] == "unsupported"


def make_cfg_repo(tmp_path, emulator_toml):
    # symport.toml lives in the repository root; use a copy so the real repo is untouched
    from tests.helpers import repo_copy
    root = repo_copy(tmp_path / "repo", with_src=False)
    (root / "symport.toml").write_text(emulator_toml)
    return root


def test_emulator_exit_zero_is_not_installation(tmp_path):
    fake = write_tool(tmp_path / "emu", "import sys; print('booted ok'); print(sys.argv[1:])")
    root = make_cfg_repo(tmp_path, f'[emulator]\ncommand = [{str(fake)!r}, "--install", "{{sis}}"]\ntimeout = 20\n'
                                   'success_marker = "booted ok"\n')
    sis = sis_file(tmp_path)
    r = sp("emulator", "test", str(sis), "--repo", str(root), "--json")
    d = json.loads(r.stdout)
    ids = {c["id"]: c for c in d["checks"]}
    assert r.returncode == 0
    assert ids["emulator.process"]["status"] == "pass" and ids["emulator.marker"]["status"] == "pass"
    assert ids["emulator.install"]["status"] == "unknown" and ids["emulator.app_start"]["status"] == "unknown"
    assert d["verification"]["emulator"] == "launched-unconfirmed"
    assert d["verification"]["physical_device"] == "not-tested"
    assert any(a["path"].endswith(".emulator.log") for a in d["artifacts"])


def test_emulator_failure_and_timeout_reported(tmp_path):
    fake = write_tool(tmp_path / "emu", "import sys; sys.exit(7)")
    root = make_cfg_repo(tmp_path, f'[emulator]\ncommand = [{str(fake)!r}, "{{sis}}"]\n')
    r = sp("emulator", "test", str(sis_file(tmp_path)), "--repo", str(root), "--json")
    d = json.loads(r.stdout)
    assert r.returncode == 1 and d["verification"]["emulator"] == "failed"
    slow = write_tool(tmp_path / "slow", "import time; time.sleep(30)")
    root2 = make_cfg_repo(tmp_path / "x", f'[emulator]\ncommand = [{str(slow)!r}]\ntimeout = 1\n')
    d = json.loads(sp("emulator", "test", str(sis_file(tmp_path)), "--repo", str(root2), "--json").stdout)
    assert next(c for c in d["checks"] if c["id"] == "emulator.process")["evidence"]["timed_out"] is True


def test_emulator_refuses_invalid_sis(tmp_path):
    junk = tmp_path / "x.sis"
    junk.write_bytes(b"x" * 50)
    r = sp("emulator", "test", str(junk), "--json")
    assert r.returncode == 1


def test_app_build_checks_architecture_before_calling_sdk(tmp_path):
    fake = write_tool(tmp_path / "symbian", FAKE_SYMBIAN)
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "symbian.toml").write_text('[project]\narchitecture = "armv6"\nname = "p"\nuid3 = 0xe0000001\n')
    r = sp("app", "build", "--project", str(proj), "--json", env={"SYMPORT_SYMBIAN": str(fake)})
    d = json.loads(r.stdout)
    assert r.returncode == 1 and any(c["id"] == "project.architecture" and c["status"] == "fail" for c in d["checks"])
    assert not (tmp_path / "symbian.calls").exists()      # SDK was not invoked for an ARMv6 project
    (proj / "symbian.toml").write_text('[project]\narchitecture = "armv5t"\nname = "p"\nuid3 = 0xe0000001\n')
    r = sp("app", "build", "--project", str(proj), "--json", env={"SYMPORT_SYMBIAN": str(fake)})
    d = json.loads(r.stdout)
    # fake SDK "succeeds" but produces no .symbian/build/p.exe -> must not be reported as success
    assert r.returncode == 1 and any(c["id"] == "build.artifact" for c in d["checks"])


def test_app_init_uses_sdk_and_armv5t(tmp_path):
    fake = write_tool(tmp_path / "symbian", FAKE_SYMBIAN)
    r = sp("app", "init", "--name", "hello", "--dest", str(tmp_path / "hello"), "--json", env={"SYMPORT_SYMBIAN": str(fake)})
    d = json.loads(r.stdout)
    calls = [json.loads(line) for line in open(str(fake) + ".calls")]
    assert r.returncode == 0 and calls[-1][:2] == ["init", str(tmp_path / "hello")] and "armv5t" in calls[-1]
    assert d["data"]["suggested_test_uids"][0].startswith("0xe")
    r = sp("app", "init", "--name", "Bad Name", "--json", env={"SYMPORT_SYMBIAN": str(fake)})
    assert r.returncode == 1


def project_with_exe(tmp_path, arch="armv5t", imports=None):
    proj = tmp_path / "proj"
    (proj / ".symbian" / "build").mkdir(parents=True)
    (proj / "symbian.toml").write_text(
        f'[project]\narchitecture = "{arch}"\nname = "hello"\nuid3 = 0xe0000001\n'
        '[package]\nuid = 0xe0000002\nname = "Hello"\nvendor = "v"\nexecutable_name = "hello.exe"\nversion = [1, 0, 0]\n')
    (proj / ".symbian" / "build" / "hello.exe").write_bytes(make_e32(uid3=0xE0000001, imports=imports))
    return proj


def test_app_inspect_and_analyze_project(tmp_path):
    proj = project_with_exe(tmp_path)
    d = json.loads(sp("app", "inspect", "--project", str(proj), "--json").stdout)
    assert d["status"] == "ok" and d["data"]["built_executable"].endswith("hello.exe")
    d = json.loads(sp("app", "analyze", str(proj), "--json").stdout)
    assert d["data"]["compatibility"]["status"] == "compatible"
    assert d["data"]["compatibility"]["runtime"] == "not-tested"
    proj2 = project_with_exe(tmp_path / "b", imports={"avkon[10003a02].dll": [5]})
    d = json.loads(sp("app", "analyze", str(proj2), "--json").stdout)
    assert d["data"]["compatibility"]["status"] == "unknown"           # firmware data missing
    unbuilt = tmp_path / "c"
    unbuilt.mkdir()
    (unbuilt / "symbian.toml").write_text('[project]\narchitecture = "armv5t"\nname = "x"\nuid3 = 0xe0000001\n')
    d = json.loads(sp("app", "analyze", str(unbuilt), "--json").stdout)
    assert d["data"]["compatibility"]["status"] == "not-tested"


def test_same_uid_for_package_and_executable_is_rejected(tmp_path):
    proj = project_with_exe(tmp_path)
    (proj / "symbian.toml").write_text('[project]\narchitecture = "armv5t"\nname = "hello"\nuid3 = 0xe0000001\n'
                                       '[package]\nuid = 0xe0000001\n')
    r = sp("app", "inspect", "--project", str(proj), "--json")
    assert r.returncode == 1 and any(c["id"] == "uid.distinct" for c in json.loads(r.stdout)["checks"])


def test_app_package_delegates_and_verifies_sis(tmp_path):
    proj = project_with_exe(tmp_path)
    out = proj / ".symbian" / "package"
    sis = sis_file(tmp_path, "made.sis")
    fake = write_tool(tmp_path / "symbian",
                      "import sys, shutil, pathlib\na = sys.argv[1:]\n"
                      "if a[0] == 'package':\n"
                      f"    out = pathlib.Path(a[a.index('--output') + 1]); out.mkdir(parents=True, exist_ok=True)\n"
                      f"    shutil.copy({str(sis)!r}, out / 'hello.sis')\n")
    r = sp("app", "package", "--project", str(proj), "--json", env={"SYMPORT_SYMBIAN": str(fake)})
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d["artifacts"][0]["path"].endswith("hello.sis")
    assert any(c["id"] == "sis.hello.sis" and c["status"] == "pass" for c in d["checks"])
    assert d["verification"]["physical_device"] == "not-tested"
    (out / "hello.sis").unlink()
    broken = write_tool(tmp_path / "symbian2", "pass")           # exits 0 but writes no package
    r = sp("app", "package", "--project", str(proj), "--json", env={"SYMPORT_SYMBIAN": str(broken)})
    assert r.returncode == 1


def test_sis_inspect_evaluates_embedded_e32(tmp_path):
    sis = sis_file(tmp_path)
    d = json.loads(sp("sis", "inspect", str(sis), "--json").stdout)
    assert d["data"]["compatibility"]["status"] == "compatible" and d["data"]["compatibility"]["images"] == 1
    assert any(c["id"] == "sis.dependencies" and c["status"] == "warn" for c in d["checks"])
    armv6 = tmp_path / "v6.sis"
    armv6.write_bytes(writer.build(writer.SisPackage(0xE0000001, "T", "v", (1, 0, 0),
                                                     [writer.SisFile("!:\\sys\\bin\\t.exe", make_e32(cpu=0x2002))])))
    d = json.loads(sp("sis", "inspect", str(armv6), "--json").stdout)
    assert d["data"]["compatibility"]["status"] == "incompatible"
