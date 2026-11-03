"""Original MIT adapter around the installed OpenOBEX/ObexFTP executable.

No protocol or GPL source is copied. Files are confined to the remote server's
exposed namespace. Writes stage into a fresh folder and require byte read-back.
OPP transfers never claim installation, phonebook import, or read-back verification.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

LIMIT = 64 * 1024 * 1024


def remote_path(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 1024
        or value.startswith("/")
        or "\\" in value
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Use a relative OBEX server path")
    parts = value.split("/") if value else []
    if any(
        p in ("", ".", "..") or (":" in p and not (i == 0 and re.fullmatch("[C-Zc-z]:", p)))
        for i, p in enumerate(parts)
    ):
        raise ValueError("Invalid OBEX server path")
    return "/".join(parts)


def parse_listing(raw: bytes) -> list[dict]:
    if (
        len(raw) > 1024 * 1024
        or b"<!ENTITY" in raw.upper()
        or b"["
        in raw[raw.upper().find(b"<!DOCTYPE") : raw.find(b">", raw.upper().find(b"<!DOCTYPE")) + 1]
    ):
        raise ValueError("Unsafe or oversized OBEX folder listing")
    start, end = raw.find(b"<?xml"), raw.rfind(b"</folder-listing>")
    if start < 0:
        start = raw.find(b"<folder-listing")
    closing = len(b"</folder-listing>")
    if end < 0:
        empty = re.search(rb"<folder-listing\b[^>]*?/>", raw)
        if empty:
            end, closing = empty.end(), 0
    if start < 0 or end < start:
        raise ValueError("OBEX did not return a folder listing")
    try:
        root = ElementTree.fromstring(raw[start : end + closing])
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid OBEX folder listing") from exc
    if root.tag != "folder-listing" or len(root) > 5000:
        raise ValueError("Unsupported OBEX folder listing")
    entries, seen = [], set()
    for node in root:
        if node.tag == "parent-folder":
            continue
        name = node.get("name")
        if node.tag not in ("file", "folder") or not name or "/" in name or name in seen:
            raise ValueError("Invalid OBEX entry")
        remote_path(name)
        seen.add(name)
        size = node.get("size")
        if size is not None and (not size.isdigit() or len(size) > 18):
            raise ValueError("Invalid OBEX file size")
        entries.append(
            {
                "name": name,
                "directory": node.tag == "folder",
                "size": int(size) if size else None,
                "modified": node.get("modified"),
            }
        )
    return entries


class ObexAdapter:
    def __init__(self, profile: dict, runner=None):
        self.profile = profile
        self.id = profile["id"]
        self.runner = runner or self._run
        self.external = runner is None

    def _base(self) -> list[str]:
        executable = os.getenv("SYMPORT_OBEXFTP_EXECUTABLE") or shutil.which("obexftp")
        if not executable:
            raise ValueError("ObexFTP is not installed on the PC connected to the phone")
        p = self.profile
        args = [executable]
        if p["transport"] == "bluetooth":
            args += ["--bluetooth", p["address"], "--channel", str(p["channel"])]
        else:
            args += ["--usb", str(p["interface"])]
        if p["kind"] == "obex-opp":
            args += ["--uuid", "none", "--noconn", "--nopath"]
        else:
            args += ["--uuid", "FBS"]
        return args

    def _run(self, options: list[str], cwd: Path | None = None) -> bytes:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                result = subprocess.run(
                    self._base() + options,
                    cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=120,
                    check=False,
                    env={**os.environ, "LC_ALL": "C"},
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ValueError(
                    "OBEX connection failed or timed out; check pairing, service and channel"
                ) from exc
            stderr.seek(0)
            diagnostic = stderr.read(16384).lower()
            # Upstream returns -1 (255) for a successful OBEX request; distro
            # variants may normalize that to zero. Content/read-back is also checked.
            if (
                result.returncode not in (0, 255)
                or b"failed:" in diagnostic
                or b"error:" in diagnostic
            ):
                raise ValueError(
                    f"OBEX request failed (exit {result.returncode}); verify the exposed service and phone permission"
                )
            stdout.seek(0, 2)
            if stdout.tell() > 1024 * 1024:
                raise ValueError("OBEX diagnostic output exceeds the safe limit")
            stdout.seek(0)
            return stdout.read()

    def listing(self, path="") -> list[dict]:
        path = remote_path(path)
        return parse_listing(self.runner(["--list", path]))

    def device(self) -> dict:
        row = {
            "id": self.id,
            "name": self.profile["name"],
            "transport": self.profile["kind"],
            "connection_kind": self.profile["transport"],
            "connected": False,
            "model": None,
            "rm": None,
            "firmware": None,
            "battery": None,
            "capabilities": [],
            "configured_target": {
                "manufacturer": "Nokia",
                "platform": "S60",
                "edition": self.profile["edition"],
            },
        }
        if self.external:
            try:
                self._base()
            except ValueError as exc:
                row.update(configured=True, evidence=str(exc))
                return row
        if self.profile["kind"] == "obex-opp":
            # OPP has no read-only folder probe. Offer an explicitly configured,
            # confirmed transfer attempt without inventing a discovered handset.
            row.update(
                configured=True,
                capabilities=["opp-push", "transfer"],
                evidence="Configured OPP endpoint; receiver acceptance is checked only during a confirmed push",
            )
            return row
        try:
            self.listing()
            row.update(
                connected=True,
                capabilities=["files", "files-list", "files-download", "files-stage", "transfer"],
                evidence="Actual OBEX folder-listing response; only the exposed namespace is accessible",
            )
        except ValueError as exc:
            row["evidence"] = str(exc)
        return row

    def _download(self, path: str, target: Path):
        parent, name = str(PurePosixPath(path).parent), PurePosixPath(path).name
        entry = next(
            (
                e
                for e in self.listing("" if parent == "." else parent)
                if e["name"] == name and not e["directory"]
            ),
            None,
        )
        if entry is None or entry["size"] is None or entry["size"] > LIMIT:
            raise ValueError(
                "OBEX download requires a listed regular file with known size up to 64 MiB"
            )
        self.runner(["--output", str(target), "--get", path], target.parent)
        if not target.is_file() or target.is_symlink() or target.stat().st_size != entry["size"]:
            raise ValueError("OBEX download was incomplete; no successful result is recorded")

    def execute(self, data: dict) -> dict:
        action, path = data["action"], remote_path(data.get("path", ""))
        if action == "connection-diagnose":
            return {"connection": self.device()}
        if action == "list" and self.profile["kind"] != "obex-opp":
            return {"entries": self.listing(path)}
        if action == "download" and self.profile["kind"] != "obex-opp":
            with tempfile.TemporaryDirectory(prefix="symport-obex-") as tmp:
                target = Path(tmp) / "payload.bin"
                self._download(path, target)
                return {
                    "name": PurePosixPath(path).name,
                    "content": base64.b64encode(target.read_bytes()).decode(),
                }
        if action in ("upload", "transfer", "software-transfer", "media-upload"):
            if data.get("confirm") is not True:
                raise ValueError("Confirm the exact OBEX transfer")
            raw = base64.b64decode(data.get("content", ""), validate=True)
            if len(raw) > (
                LIMIT
                if action == "media-upload"
                else 32 * 1024 * 1024
                if action in ("transfer", "software-transfer")
                else 8 * 1024 * 1024
            ):
                raise ValueError("OBEX transfer exceeds the size limit")
            name = PurePosixPath(path).name
            if not name or ":" in name:
                raise ValueError("Choose a file name")
            if action in ("transfer", "software-transfer"):
                from symport.catalog.packages import validate_package

                validate_package(name, raw)
                if PurePosixPath(name).suffix.lower() == ".jad":
                    raise ValueError("OBEX staging cannot preserve a JAR/JAD pair. Transfer a JAR-only package or use a mounted memory card.")
            if action == "media-upload":
                allowed = {
                    "audio": {".mp3", ".aac", ".m4a", ".wav", ".mid", ".midi", ".amr"},
                    "video": {".mp4", ".3gp"},
                }
                if PurePosixPath(name).suffix.lower() not in allowed.get(data.get("kind"), set()):
                    raise ValueError("Unsupported media type")
            with tempfile.TemporaryDirectory(prefix="symport-obex-") as tmp:
                source = Path(tmp) / "payload.bin"
                source.write_bytes(raw)
                if self.profile["kind"] == "obex-opp":
                    if len(PurePosixPath(path).parts) != 1:
                        raise ValueError(
                            "OPP sends a file to the phone inbox; it cannot select a destination folder"
                        )
                    self.runner(["--output", name, "--put", str(source)], Path(tmp))
                    return {
                        "status": "received-by-opp-not-installed",
                        "verification": "receiver-acknowledgement-only",
                        "destination": "phone inbox",
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                parent = str(PurePosixPath(path).parent)
                parent = "" if parent == "." else parent
                upper = parent.upper()
                if upper.startswith("Z:") or any(
                    upper == prefix or upper.startswith(prefix + "/")
                    for prefix in ("C:/SYS", "C:/PRIVATE", "C:/SYSTEM")
                ):
                    raise ValueError(
                        "OBEX staging is limited to public user folders; system and ROM paths are blocked"
                    )
                folder = "SymPort-transfer-" + secrets.token_hex(12)
                if any(e["name"] == folder for e in self.listing(parent)):
                    raise ValueError("Staging folder already exists; retry with a new transfer")
                stage = "/".join(filter(None, (parent, folder)))
                self.runner(["--mkdir", stage], Path(tmp))
                if self.listing(stage):
                    raise ValueError("The staging folder is not empty; no file was sent")
                destination = "/".join((stage, name))
                # One operation: ObexFTP's library resolves the full remote name
                # and returns before PUT if SETPATH fails. Chained CLI -c/-p can
                # continue after a failed chdir and would risk writing at root.
                self.runner(["--output", destination, "--put", str(source)], Path(tmp))
                downloaded = Path(tmp) / "readback.bin"
                self._download(destination, downloaded)
                if hashlib.sha256(downloaded.read_bytes()).digest() != hashlib.sha256(raw).digest():
                    raise ValueError(
                        "OBEX read-back differs; inspect the staged folder before another transfer"
                    )
                return {
                    "status": "transferred-not-installed"
                    if action in ("transfer", "software-transfer")
                    else "verified-by-readback",
                    "destination": destination,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
        raise ValueError(
            "This OBEX service does not provide this operation. Delete, overwrite, phonebook, SMS and calendar are unavailable through this adapter"
        )
