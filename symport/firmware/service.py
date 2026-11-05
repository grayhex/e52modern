"""Firmware & ROM Explorer actions: browse, search, inspect, dependencies and comparison."""
from __future__ import annotations

from pathlib import Path

from symport.analysis import e32

from .index import FirmwareError, read_member
from .store import FirmwareStore

LIMIT = 500


def _lite(entry: dict) -> dict:
    out = {k: entry.get(k) for k in ("path", "name", "dir", "size", "kind", "basis", "sha256", "uids")}
    e = entry.get("e32")
    if e:
        out["e32"] = {k: e[k] for k in ("capabilities", "is_dll", "secure_id", "compression", "module_version", "kernel", "cpu")}
        out["e32"]["imports_known"] = e["imports"] is not None
    if entry.get("parse_error"):
        out["parse_error"] = entry["parse_error"]
    return out


def _limit(value, default=100) -> int:
    if value is None:
        return default
    if type(value) is not int or not 1 <= value <= LIMIT:
        raise FirmwareError(f"limit must be 1–{LIMIT}")
    return value


def _tree(index: dict) -> dict:
    tree = index.get("_tree")
    if tree is None:
        tree = {}
        for entry in index["entries"]:
            parts = entry["path"].split("/")
            for depth in range(1, len(parts)):
                directory = "/".join(parts[:depth])
                node = tree.setdefault(directory.lower(), {"dirs": {}, "files": []})
                if depth == len(parts) - 1:
                    node["files"].append(entry)
                child = parts[depth] if depth < len(parts) - 1 else None
                if child:
                    count = node["dirs"].setdefault(child, [0, 0])
                    count[0] += 1
                    count[1] += entry["size"]
        index["_tree"] = tree
    return tree


def _basenames(index: dict) -> dict:
    names = index.get("_basenames")
    if names is None:
        names = {}
        for entry in index["entries"]:
            if entry["kind"] in ("e32-dll", "e32-exe", "rom-image-dll", "rom-image-exe"):
                names.setdefault(entry["name"].lower(), entry)
        index["_basenames"] = names
    return names


def _importers(index: dict) -> dict:
    reverse = index.get("_importers")
    if reverse is None:
        reverse = {}
        for entry in index["entries"]:
            for imp in (entry.get("e32") or {}).get("imports") or []:
                reverse.setdefault(imp.lower(), []).append(entry["path"])
        index["_importers"] = reverse
    return reverse


class FirmwareExplorer:
    def __init__(self, root: Path):
        self.store = FirmwareStore(Path(root))

    def execute(self, data: dict) -> dict:
        action = data.get("action")
        if action == "list":
            return {"images": self.store.list(), "limits": {"max_images": 6}}
        if action == "delete":
            return self.store.delete(data.get("id"), data.get("confirm"))
        key = data.get("id")
        if action == "status":
            meta = self.store._meta(key)
            if meta["status"] == "ready":
                index = self.store.index(key)
                meta = {**meta, "counts": index["counts"], "source": index["source"], "skipped": index["skipped"],
                        "skipped_count": index["skipped_count"], "levels": index["levels"], "limitations": index["limitations"],
                        "rom": index.get("rom")}
            return meta
        if action == "children":
            index = self.store.index(key)
            raw = str(data.get("dir") or "Z:").replace("\\", "/")
            if not raw.upper().startswith("Z:") or ".." in raw.split("/"):
                raise FirmwareError("Invalid directory")
            rest = [p for p in raw[2:].split("/") if p]
            base = "Z:" + "".join("/" + p for p in rest)
            node = _tree(index).get(base.lower()) or {"dirs": {}, "files": []}
            return {"dir": base, "folders": [{"name": n, "path": base + "/" + n, "files": c[0], "bytes": c[1]}
                                             for n, c in sorted(node["dirs"].items(), key=lambda kv: kv[0].lower())],
                    "files": [_lite(e) for e in sorted(node["files"], key=lambda e: e["name"].lower())[:2000]],
                    "files_total": len(node["files"])}
        if action == "search":
            index = self.store.index(key)
            query = str(data.get("query") or "").casefold()
            kind, uid = data.get("kind"), str(data.get("uid") or "").lower()
            capability = data.get("capability")
            limit, offset = _limit(data.get("limit")), data.get("offset", 0)
            if type(offset) is not int or offset < 0:
                raise FirmwareError("Invalid offset")
            hits = []
            for entry in index["entries"]:
                e = entry.get("e32") or {}
                if query and query not in entry["path"].casefold():
                    continue
                if kind and entry["kind"] != kind:
                    continue
                if uid and not any(uid in u for u in (entry.get("uids") or []) + ([e["secure_id"]] if e.get("secure_id") else [])):
                    continue
                if capability and capability not in (e.get("capabilities") or []):
                    continue
                hits.append(entry)
            return {"total": len(hits), "offset": offset, "entries": [_lite(e) for e in hits[offset:offset + limit]]}
        if action == "file":
            index = self.store.index(key)
            entry = index["_lookup"].get(str(data.get("path") or "").lower())
            if not entry:
                raise FirmwareError("File not found in this firmware")
            result = {"entry": entry, "hex_head": None, "e32_full": None}
            try:
                blob = read_member(self.store.source_path(key), index["source"]["kind"], entry)
                result["hex_head"] = blob[:256].hex()
                if entry["kind"] in ("e32-exe", "e32-dll"):
                    result["e32_full"] = e32.analyze(blob)
            except (FirmwareError, e32.E32Error, ValueError) as exc:
                result["read_error"] = str(exc)[:200]
            return result
        if action == "dependencies":
            index = self.store.index(key)
            entry = index["_lookup"].get(str(data.get("path") or "").lower())
            if not entry:
                raise FirmwareError("File not found in this firmware")
            names, reverse = _basenames(index), _importers(index)
            imports = (entry.get("e32") or {}).get("imports")
            return {"path": entry["path"], "imports_known": imports is not None,
                    "imports": None if imports is None else [
                        {"name": n, "resolved": (names.get(n.lower()) or {}).get("path"),
                         "status": "present-in-image" if n.lower() in names else "missing-from-image"} for n in imports],
                    "imported_by": sorted(reverse.get(entry["name"].lower(), []))[:200],
                    "note": None if imports is not None else "Imports are not available for this file (compressed image, ROM-resident image or not E32)."}
        if action == "compare":
            return self._compare(data)
        if action == "profile":
            index = self.store.index(key)
            version = str(data.get("firmware_version") or "").strip()
            if not 1 <= len(version) <= 120:
                raise FirmwareError("Enter the exact firmware version this image belongs to")
            from symport.phone.registry import selectable_profiles
            selected = data.get("profile", "nokia-e52")
            profile = selectable_profiles().get(selected)
            if not profile:
                raise FirmwareError("Choose an exact Nokia model profile")
            dlls = {e["name"].lower(): {} for e in index["entries"] if e["kind"] in ("e32-dll", "rom-image-dll")}
            return {"schema": 1, "id": "firmware-" + key, "device": selected, "firmware_version": version, "platform": profile["s60"], "symbian": profile["symbian"], "model_evidence": "user-declared; not inferred from firmware",
                    "source": "firmware-explorer:" + index["source"]["sha256"], "dlls": dlls,
                    "note": "DLL names only; export ordinals are unknown, so ordinal-level compatibility stays unknown."}
        raise FirmwareError("Unknown firmware operation")

    def dll_names(self, key) -> tuple[set[str], str]:
        """DLL file names in an indexed image (used by dependency analysis as firmware data)."""
        index = self.store.index(key)
        return ({e["name"].lower() for e in index["entries"] if e["kind"] in ("e32-dll", "rom-image-dll")},
                "firmware-explorer:" + index["source"]["sha256"][:16])

    def _compare(self, data: dict) -> dict:
        a, b = self.store.index(data.get("a")), self.store.index(data.get("b"))
        limit = _limit(data.get("limit"), 200)
        ea = {e["path"].lower(): e for e in a["entries"]}
        eb = {e["path"].lower(): e for e in b["entries"]}
        only_a = sorted(k for k in ea if k not in eb)
        only_b = sorted(k for k in eb if k not in ea)
        changed, identical = [], 0
        for k in sorted(ea.keys() & eb.keys()):
            x, y = ea[k], eb[k]
            same = x["sha256"] == y["sha256"] if x["sha256"] and y["sha256"] else x["size"] == y["size"]
            if same:
                identical += 1
                continue
            item = {"path": x["path"], "kind": x["kind"], "a": {"size": x["size"], "sha256": x["sha256"]},
                    "b": {"size": y["size"], "sha256": y["sha256"]}, "details": {}}
            ex, ey = x.get("e32"), y.get("e32")
            if ex and ey:
                for field in ("module_version", "secure_id", "kernel", "cpu", "compression"):
                    if ex[field] != ey[field]:
                        item["details"][field] = [ex[field], ey[field]]
                if set(ex["capabilities"] or []) != set(ey["capabilities"] or []):
                    item["details"]["capabilities"] = {"added": sorted(set(ey["capabilities"] or []) - set(ex["capabilities"] or [])),
                                                       "removed": sorted(set(ex["capabilities"] or []) - set(ey["capabilities"] or []))}
                if ex["imports"] is not None and ey["imports"] is not None and set(ex["imports"]) != set(ey["imports"]):
                    item["details"]["imports"] = {"added": sorted(set(ey["imports"]) - set(ex["imports"])),
                                                  "removed": sorted(set(ex["imports"]) - set(ey["imports"]))}
            changed.append(item)
        return {"a": {"id": data.get("a"), "name": a["source"]["name"], "files": a["counts"]["files"]},
                "b": {"id": data.get("b"), "name": b["source"]["name"], "files": b["counts"]["files"]},
                "summary": {"only_a": len(only_a), "only_b": len(only_b), "changed": len(changed), "identical": identical,
                            "e32_changed": sum(1 for c in changed if c["details"])},
                "only_a": [ea[k]["path"] for k in only_a[:limit]], "only_b": [eb[k]["path"] for k in only_b[:limit]],
                "changed": changed[:limit], "truncated": {"only_a": len(only_a) > limit, "only_b": len(only_b) > limit,
                                                          "changed": len(changed) > limit},
                "basis": "SHA-256 per path (size when a file was too large to hash); static comparison only."}
