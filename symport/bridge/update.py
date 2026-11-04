"""Update check for the installed Windows Bridge: ask first, verify everything, never silent.

Trust model (no paid Authenticode certificate):

* the release list comes from the GitHub API of this project over HTTPS, and every download URL
  must stay on GitHub's release hosts and under exactly this project's ``bridge-vX.Y.Z`` release;
* the manifest states version, size and SHA-256 of the installer; a newer version is required
  (no downgrade) and the downloaded file must match size and hash before it is ever executed;
* when ``UPDATE_PUBLIC_KEY`` is set, the manifest must also carry a valid Ed25519 signature, so a
  tampered release asset is rejected even if someone could replace files on the release;
* nothing is downloaded or installed without the user confirming the exact version, and the
  installer is not started while a phone operation is running.

Windows SmartScreen still shows its "unknown publisher" warning for unsigned installers.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import VERSION, ed25519

REPO = "grayhex/s60modern"
TAG_RE = re.compile(r"^bridge-v(\d+\.\d+\.\d+)$")
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
RELEASE_HOSTS = (
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
)
MANIFEST_NAME = "bridge-update.json"
SCHEMA = "symport.bridge-update/1"
# Hex Ed25519 public key (64 characters) that signs bridge-update.json in the release workflow.
# Empty until the project owner creates the key (see docs/WINDOWS_BRIDGE.md); then it is required.
UPDATE_PUBLIC_KEY = ""
MAX_INSTALLER = 300 * 1024 * 1024
CHECK_INTERVAL = 24 * 3600


class UpdateError(Exception):
    """A fixed, user-safe explanation; never raw network or file-system text."""


@dataclass(frozen=True)
class Update:
    version: str
    name: str
    url: str
    size: int
    sha256: str
    notes: str
    released: str
    signed: bool


def parse_version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d{1,4})\.(\d{1,4})\.(\d{1,4})", str(value))
    if not match:
        raise UpdateError("Invalid version number")
    return int(match[1]), int(match[2]), int(match[3])


def canonical(manifest: dict) -> bytes:
    body = {k: v for k, v in manifest.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def host_allowed(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and parts.hostname in RELEASE_HOSTS
        and not parts.username
        and not parts.password
        and parts.port in (None, 443)
    )


def validate_manifest(
    manifest: object, current: str = VERSION, public_key: str = UPDATE_PUBLIC_KEY
) -> Update | None:
    """Return the update when ``manifest`` is genuine and newer than ``current``, else ``None``."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise UpdateError("The update manifest is not valid")
    version = str(manifest.get("version", ""))
    parse_version(version)
    signed = False
    if public_key:
        try:
            signature = base64.b64decode(str(manifest.get("signature", "")), validate=True)
            ok = ed25519.verify(bytes.fromhex(public_key), canonical(manifest), signature)
        except ValueError:
            ok = False
        if not ok:
            raise UpdateError("The update signature is not valid; it was ignored")
        signed = True
    installer = manifest.get("installer")
    if not isinstance(installer, dict):
        raise UpdateError("The update manifest is not valid")
    name, url = str(installer.get("name", "")), str(installer.get("url", ""))
    size, digest = installer.get("size"), str(installer.get("sha256", ""))
    expected_url = f"https://github.com/{REPO}/releases/download/bridge-v{version}/{name}"
    if (
        not re.fullmatch(r"SymPortBridge-Setup-\d+\.\d+\.\d+\.exe", name)
        or name != f"SymPortBridge-Setup-{version}.exe"
        or url != expected_url
        or not host_allowed(url)
        or type(size) is not int
        or not 1024 <= size <= MAX_INSTALLER
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        raise UpdateError("The update manifest is not valid")
    if parse_version(version) <= parse_version(current):
        return None
    notes = str(manifest.get("notes", ""))[:2000]
    return Update(version, name, url, size, digest, notes, str(manifest.get("released", ""))[:32], signed)


class _Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not host_allowed(newurl):
            raise UpdateError("The download was redirected to an unexpected host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_fetch(url: str, limit: int = 1024 * 1024) -> bytes:
    if not host_allowed(url):
        raise UpdateError("Unexpected update host")
    request = Request(url, headers={"User-Agent": "SymPortBridge/" + VERSION, "Accept": "application/json"})
    try:
        with build_opener(_Redirects()).open(request, timeout=20) as response:
            raw = response.read(limit + 1)
    except UpdateError:
        raise
    except OSError as exc:
        raise UpdateError("The update server could not be reached") from exc
    if len(raw) > limit:
        raise UpdateError("The update response is too large")
    return raw


def latest_manifest(fetch=default_fetch) -> dict | None:
    try:
        releases = json.loads(fetch(RELEASES_URL))
    except ValueError as exc:
        raise UpdateError("The release list is not valid") from exc
    best, best_version = None, (-1, 0, 0)
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        match = TAG_RE.fullmatch(str(release.get("tag_name", "")))
        if match and parse_version(match[1]) > best_version:
            best, best_version = release, parse_version(match[1])
    if best is None:
        return None
    asset = next(
        (a for a in best.get("assets") or [] if isinstance(a, dict) and a.get("name") == MANIFEST_NAME),
        None,
    )
    if asset is None:
        return None
    try:
        manifest = json.loads(fetch(str(asset.get("browser_download_url", ""))))
    except ValueError as exc:
        raise UpdateError("The update manifest is not valid") from exc
    # The manifest must describe the release it was published with.
    if isinstance(manifest, dict) and f"bridge-v{manifest.get('version')}" != best.get("tag_name"):
        raise UpdateError("The update manifest does not match its release")
    return manifest


def check(current: str = VERSION, fetch=default_fetch, public_key: str = UPDATE_PUBLIC_KEY) -> Update | None:
    manifest = latest_manifest(fetch)
    return None if manifest is None else validate_manifest(manifest, current, public_key)


def download(update: Update, directory: Path, progress=None, opener=None) -> Path:
    """Fetch the installer into ``directory``; the file exists under its final name only if verified."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / update.name
    part = directory / (update.name + ".part")
    if not host_allowed(update.url):
        raise UpdateError("Unexpected update host")
    request = Request(update.url, headers={"User-Agent": "SymPortBridge/" + VERSION})
    digest, received = hashlib.sha256(), 0
    try:
        with (opener or build_opener(_Redirects())).open(request, timeout=30) as response:
            with part.open("wb") as output:
                while True:
                    block = response.read(256 * 1024)
                    if not block:
                        break
                    received += len(block)
                    if received > update.size:
                        raise UpdateError("The download is larger than announced")
                    digest.update(block)
                    output.write(block)
                    if progress:
                        progress(received, update.size)
        if received != update.size or digest.hexdigest() != update.sha256:
            raise UpdateError("The downloaded installer does not match its announced hash")
        os.replace(part, target)
        return target
    except UpdateError:
        part.unlink(missing_ok=True)
        raise
    except OSError as exc:
        part.unlink(missing_ok=True)
        raise UpdateError("The download failed") from exc


def installed() -> bool:
    """True for the Inno Setup installation (it leaves an uninstaller next to the executable)."""
    return bool(getattr(sys, "frozen", False)) and any(
        Path(sys.executable).parent.glob("unins???.exe")
    )


def launch_installer(path: Path) -> None:
    """Start the verified installer detached; it closes this application and restarts it."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/StartAfter=1"],
        close_fds=True,
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def due(last_check: float | None, now: float | None = None) -> bool:
    return last_check is None or (now if now is not None else time.time()) - last_check >= CHECK_INTERVAL


def _state_path(root: Path) -> Path:
    return root / "update-state.json"


def load_state(root: Path) -> dict:
    try:
        path = _state_path(root)
        if path.is_symlink() or path.stat().st_size > 4096:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(root: Path, state: dict) -> None:
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        _state_path(root).write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass  # a missing throttle record only means one extra check


def describe(found: Update) -> str:
    return (
        f"SymPort Bridge {found.version} is available (installed: {VERSION}).\n\n"
        + (found.notes.strip() + "\n\n" if found.notes.strip() else "")
        + f"Installer: {found.name} ({found.size / 1024 / 1024:.1f} MiB)\n"
        + f"SHA-256: {found.sha256[:16]}…  ·  "
        + ("signed by the SymPort release key" if found.signed else "not signed (checksum only)")
        + "\n\nDownload and install now? Phone operations in progress are never interrupted, "
        "and nothing is installed without this confirmation."
    )


def run_flow(
    root: Path,
    *,
    interactive: bool,
    ask,
    inform,
    notify=None,
    fetch=default_fetch,
    public_key: str = UPDATE_PUBLIC_KEY,
    downloader=download,
    idle=lambda: True,
    launch=launch_installer,
    is_installed=installed,
    now=time.time,
    current: str = VERSION,
) -> str:
    """One update pass. ``ask(text) -> bool`` and ``inform(text)`` talk to the user.

    Automatic passes (``interactive=False``) only look and notify once per version; they never
    download. Returns a short status used by tests and diagnostics.
    """
    state = load_state(root)
    try:
        found = check(current, fetch, public_key)
    except UpdateError as exc:
        if interactive:
            inform(str(exc))
        return "error"
    finally:
        state["last_check"] = now()
        save_state(root, state)
    if found is None:
        if interactive:
            inform(f"SymPort Bridge {current} is up to date.")
        return "up-to-date"
    if not interactive:
        if state.get("notified") != found.version and notify:
            notify(f"SymPort Bridge {found.version} is available. Open the tray menu to install it.")
            save_state(root, {**state, "notified": found.version})
            return "notified"
        return "already-notified"
    if not is_installed():
        # Portable copy: no installer to run over it. Point to the release instead.
        inform(
            f"SymPort Bridge {found.version} is available.\n\nThis portable copy cannot update itself. "
            "Download the installer from the project's GitHub Releases page."
        )
        return "portable"
    if not ask(describe(found)):
        return "declined"
    try:
        path = downloader(found, root / "updates")
    except UpdateError as exc:
        inform(str(exc))
        return "error"
    if not idle():
        inform("A phone operation is running. The installer is downloaded and verified; try again when it finishes.")
        return "busy"
    launch(path)
    return "launched"
