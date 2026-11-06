"""Deployment helpers: the Proxmox LXC script (checked with --dry-run) and the Docker dependency layer."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "proxmox" / "create-lxc.sh"
bash = shutil.which("bash")
pytestmark = pytest.mark.skipif(bash is None, reason="bash is required")


def dry_run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [bash, str(SCRIPT), "--dry-run", *args], capture_output=True, text=True, timeout=30
    )


def test_script_is_valid_bash():
    assert subprocess.run([bash, "-n", str(SCRIPT)]).returncode == 0


def test_dry_run_builds_an_unprivileged_container_with_docker_features():
    result = dry_run("--ctid", "120", "--storage", "local-zfs", "--bridge", "vmbr1", "--memory", "3072")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "pct create 120" in out
    assert "--unprivileged 1" in out and "--unprivileged 0" not in out
    assert "nesting=1" in out and "keyctl=1" in out
    assert "local-zfs:12" in out and "bridge=vmbr1" in out and "--memory 3072" in out
    assert "docker-compose-plugin" in out and "compose.deploy.yaml" in out


def test_nothing_is_published_beyond_the_container_loopback():
    out = dry_run().stdout
    assert "0.0.0.0" not in out and "SYMPORT_BIND" not in out
    assert "127.0.0.1:8765" in out


@pytest.mark.parametrize(
    "args",
    [("--memory", "lots"), ("--cores", "2;reboot"), ("--hostname", "bad name"), ("--nope",)],
)
def test_invalid_arguments_are_rejected_before_anything_runs(args):
    result = dry_run(*args)
    assert result.returncode == 2
    assert "pct create" not in result.stdout


def test_docker_requirements_come_from_pyproject_extras():
    out = subprocess.run(
        [sys.executable, "-I", str(ROOT / "tools" / "docker" / "requirements.py"), str(ROOT / "pyproject.toml")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    names = {line.split(">")[0].split("<")[0].split("=")[0] for line in out}
    assert {"vobject", "cryptography", "pillow", "python-gammu", "pyserial"} <= names
    assert "pytest" not in names and "pyinstaller" not in names


def test_dockerfile_installs_dependencies_before_copying_the_sources():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert text.index("requirements.py") < text.index("COPY . .")
    assert text.index("tools/s60/build.sh") < text.index("COPY . .")
    assert "HEALTHCHECK" in text and "USER 10001:10001" in text
