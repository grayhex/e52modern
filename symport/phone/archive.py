"""Full file backup of an enrolled volume: recursive, streamed, manifest with SHA-256.

Complements the small ZIP backup of one folder in ``files.py`` (8 MiB / 500 files, no subdirectories):
this engine handles a whole memory card. It never deletes, never overwrites on restore, never
follows symlinks and never stores the absolute source path.

A backup is a directory::

    <dest>/manifest.json      schema, counters, per-file size / SHA-256 / mtime, skipped items
    <dest>/manifest.sha256    SHA-256 of manifest.json (detects manifest tampering)
    <dest>/files/<relpath>    copies of the files

It is a *file* backup. It does not contain contacts, SMS, calendar, the installed-application
registry on the phone memory, or firmware (see docs/ROADMAP.md).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from .files import MountedVolumes

SCHEMA = "symport.backup/1"
CHUNK = 1 << 20
DEFAULT_MAX_FILES = 200_000
DEFAULT_MAX_BYTES = 64 * 1024**3


class BackupError(ValueError):
    pass


@dataclass
class Skipped:
    path: str
    reason: str


@dataclass
class CreateResult:
    dest: Path
    files: int
    bytes: int
    skipped: list[Skipped] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.skipped


def _rel(path: Path, root: Path) -> str:
    return PurePosixPath(*path.relative_to(root).parts).as_posix()


def _walk(root: Path, exclude: tuple[str, ...]):
    """Yield (file path, size) for regular files; record symlinks/specials as skipped."""
    skipped: list[Skipped] = []
    files: list[tuple[Path, int]] = []

    def excluded(rel: str) -> bool:
        low = rel.lower()
        return any(low == e.lower().strip("/") or low.startswith(e.lower().strip("/") + "/") for e in exclude)

    for current, dirs, names in os.walk(root, followlinks=False):
        cur = Path(current)
        keep = []
        for d in sorted(dirs):
            p = cur / d
            rel = _rel(p, root)
            if p.is_symlink():
                skipped.append(Skipped(rel, "symlink (not followed)"))
            elif excluded(rel):
                skipped.append(Skipped(rel, "excluded by request"))
            else:
                keep.append(d)
        dirs[:] = keep
        for n in sorted(names):
            p = cur / n
            rel = _rel(p, root)
            if excluded(rel):
                skipped.append(Skipped(rel, "excluded by request"))
            elif p.is_symlink():
                skipped.append(Skipped(rel, "symlink (not followed)"))
            elif not p.is_file():
                skipped.append(Skipped(rel, "not a regular file"))
            else:
                try:
                    files.append((p, p.stat().st_size))
                except OSError as e:
                    skipped.append(Skipped(rel, f"unreadable: {e.strerror or e}"))
    return files, skipped


def _copy_hashed(src: Path, dst: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    with open(src, "rb") as fi, open(tmp, "wb") as fo:
        for chunk in iter(lambda: fi.read(CHUNK), b""):
            h.update(chunk)
            fo.write(chunk)
            n += len(chunk)
    os.replace(tmp, dst)
    st = src.stat()
    os.utime(dst, ns=(st.st_atime_ns, st.st_mtime_ns))
    return h.hexdigest(), n


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def create(volume: Path, dest: Path, *, label: str = "volume", exclude: tuple[str, ...] = (),
           max_files: int = DEFAULT_MAX_FILES, max_bytes: int = DEFAULT_MAX_BYTES,
           progress=None) -> CreateResult:
    volume, dest = Path(volume), Path(dest)
    if not volume.is_dir() or volume.is_symlink():
        raise BackupError("source volume is not a directory (or is a symlink)")
    if dest.exists() and any(dest.iterdir()):
        raise BackupError("destination exists and is not empty; refusing to overwrite a backup")
    if volume.resolve() in (dest.resolve(), *dest.resolve().parents) or dest.resolve() in volume.resolve().parents:
        raise BackupError("destination must not be inside the source volume (or contain it)")

    files, skipped = _walk(volume, exclude)
    total = sum(s for _, s in files)
    if len(files) > max_files or total > max_bytes:
        raise BackupError(f"volume exceeds limits ({len(files)} files / {total} bytes; "
                          f"max {max_files} files / {max_bytes} bytes)")
    dest.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(dest).free
    if free < total + total // 20 + 1024 * 1024:
        raise BackupError(f"not enough free space at destination ({free} bytes free, {total} needed)")

    entries = []
    copied = 0
    for i, (path, size) in enumerate(files, 1):
        rel = _rel(path, volume)
        try:
            digest, n = _copy_hashed(path, dest / "files" / rel)
        except OSError as e:
            skipped.append(Skipped(rel, f"read/write failed: {e.strerror or e}"))
            continue
        if n != size or path.stat().st_size != size:
            skipped.append(Skipped(rel, "changed while it was being copied"))
            (dest / "files" / rel).unlink(missing_ok=True)
            continue
        st = path.stat()
        entries.append({"path": rel, "size": n, "sha256": digest, "mtime_ns": st.st_mtime_ns})
        copied += n
        if progress:
            progress(i, len(files), rel)
    manifest = {
        "schema": SCHEMA, "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_label": label, "complete": not skipped,
        "totals": {"files": len(entries), "bytes": copied},
        "files": entries, "skipped": [s.__dict__ for s in skipped],
        "note": "File backup only: no contacts, SMS, calendar, phone-memory application registry or firmware.",
    }
    raw = json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=False).encode("utf-8")
    (dest / "manifest.json").write_bytes(raw)
    (dest / "manifest.sha256").write_text(hashlib.sha256(raw).hexdigest() + "  manifest.json\n", encoding="ascii")
    return CreateResult(dest, len(entries), copied, skipped)


def load_manifest(backup: Path) -> dict:
    backup = Path(backup)
    mp = backup / "manifest.json"
    if not mp.is_file():
        raise BackupError("manifest.json not found: not a SymPort backup")
    raw = mp.read_bytes()
    sp = backup / "manifest.sha256"
    if sp.is_file():
        want = sp.read_text(encoding="ascii", errors="replace").split()[0]
        if hashlib.sha256(raw).hexdigest() != want:
            raise BackupError("manifest.json does not match manifest.sha256 (modified or damaged)")
    else:
        raise BackupError("manifest.sha256 missing: cannot trust the manifest")
    try:
        m = json.loads(raw)
    except ValueError as e:
        raise BackupError(f"manifest is not valid JSON: {e}") from e
    if m.get("schema") != SCHEMA or not isinstance(m.get("files"), list):
        raise BackupError("unsupported manifest schema")
    return m


def _parents_within(path: Path, root: Path):
    for p in path.parents:
        if p == root:
            return
        yield p


def _safe_rel(rel: str) -> str:
    """Same rules as the Device Manager: relative POSIX path, no traversal/ADS/reserved names."""
    if not isinstance(rel, str) or not rel:
        raise BackupError("empty path in manifest")
    if rel.startswith("/") or "\\" in rel or "\0" in rel or any(
            p in ("", ".", "..") or ":" in p or p.endswith((" ", ".")) for p in rel.split("/")):
        raise BackupError(f"unsafe path in manifest: {rel!r}")
    return rel


def verify(backup: Path) -> dict:
    """Re-hash every file. Returns counters and the lists of problems."""
    m = load_manifest(backup)
    root = Path(backup) / "files"
    missing, mismatched, unsafe = [], [], []
    listed = set()
    for e in m["files"]:
        try:
            rel = _safe_rel(e["path"])
        except BackupError:
            unsafe.append(str(e.get("path")))
            continue
        listed.add(rel)
        p = root / rel
        if p.is_symlink() or not p.is_file():
            missing.append(rel)
        elif p.stat().st_size != e["size"] or sha256_file(p) != e["sha256"]:
            mismatched.append(rel)
    extra = []
    if root.is_dir():
        for cur, _d, names in os.walk(root):
            for n in names:
                rel = _rel(Path(cur) / n, root)
                if rel not in listed:
                    extra.append(rel)
    return {"ok": not (missing or mismatched or extra or unsafe), "checked": len(listed),
            "missing": missing, "mismatched": mismatched, "extra": extra, "unsafe": unsafe,
            "complete_at_creation": bool(m.get("complete")), "skipped_at_creation": m.get("skipped", [])}


def restore(backup: Path, target: Path, *, apply: bool = False, only: str | None = None) -> dict:
    """Plan (default) or perform a restore. Never overwrites, never deletes.

    ``new`` files are copied (when ``apply``); files already identical are left; files that exist with
    different content are reported as ``conflict`` and left untouched.
    """
    m = load_manifest(backup)
    target = Path(target)
    if not target.is_dir() or target.is_symlink():
        raise BackupError("target volume is not a directory (or is a symlink)")
    vol = MountedVolumes({"t": str(target)})
    src_root = Path(backup) / "files"
    plan = {"new": [], "identical": [], "conflict": [], "blocked": []}
    todo: list[tuple[dict, Path]] = []
    for e in m["files"]:
        rel = _safe_rel(e["path"])
        if only and not (rel == only or rel.startswith(only.rstrip("/") + "/")):
            continue
        try:
            dst = vol._path("t", rel)
        except ValueError as exc:
            plan["blocked"].append({"path": rel, "reason": str(exc)})
            continue
        if dst.exists() or dst.is_symlink():
            if dst.is_file() and not dst.is_symlink() and dst.stat().st_size == e["size"] \
                    and sha256_file(dst) == e["sha256"]:
                plan["identical"].append(rel)
            else:
                plan["conflict"].append(rel)
        elif any(p.is_file() for p in _parents_within(dst, target)):
            plan["blocked"].append({"path": rel, "reason": "a parent path component is a file"})
        else:
            plan["new"].append(rel)
            todo.append((e, dst))
    need = sum(e["size"] for e, _ in todo)
    free = shutil.disk_usage(target).free
    result = {"applied": False, "plan": {k: len(v) for k, v in plan.items()}, "details": plan,
              "bytes_needed": need, "bytes_free": free, "written": 0, "verified": 0, "failed": []}
    if not apply:
        return result
    if free < need + 1024 * 1024:
        raise BackupError(f"not enough free space on the target ({free} free, {need} needed)")
    bad = verify(backup)
    if bad["missing"] or bad["mismatched"] or bad["unsafe"]:
        raise BackupError("backup failed verification; refusing to restore from a damaged backup")
    result["applied"] = True
    for e, dst in todo:
        try:
            digest, _n = _copy_hashed(src_root / e["path"], dst)
        except OSError as exc:
            result["failed"].append({"path": e["path"], "reason": exc.strerror or str(exc)})
            continue
        result["written"] += 1
        if digest == e["sha256"] and sha256_file(dst) == e["sha256"]:
            result["verified"] += 1
        else:
            result["failed"].append({"path": e["path"], "reason": "read-back hash mismatch"})
    return result
