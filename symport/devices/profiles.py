"""Declarative device profiles (profiles/*.toml).

Every fact is a table ``{ value, status, source }`` so unverified information is never
presented as confirmed. ``status`` is one of: documented, stated, inferred, unknown.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

STATUSES = {"documented", "stated", "inferred", "unknown"}


class ProfileError(Exception):
    pass


@dataclass
class Profile:
    id: str
    data: dict
    path: Path

    def fact(self, dotted: str) -> dict:
        """Return the fact table at ``dotted`` (e.g. ``platform.kernel``)."""
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return {"value": None, "status": "unknown", "source": "not present in profile"}
            node = node[part]
        if not (isinstance(node, dict) and "status" in node):
            return {"value": node, "status": "stated", "source": str(self.path)}
        return node

    def value(self, dotted: str, default=None):
        f = self.fact(dotted)
        return default if f.get("value") in (None, "", []) else f["value"]

    def known(self, dotted: str) -> bool:
        return self.fact(dotted).get("status") != "unknown" and self.fact(dotted).get("value") is not None

    def facts(self) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []

        def walk(prefix: str, node: dict) -> None:
            for k, v in node.items():
                if isinstance(v, dict):
                    if "status" in v and "value" in v:
                        out.append((f"{prefix}{k}", v))
                    else:
                        walk(f"{prefix}{k}.", v)
        walk("", self.data)
        return out

    def summary(self) -> dict:
        facts = self.facts()
        return {
            "id": self.id, "path": str(self.path),
            "name": f"{self.value('device.manufacturer', '?')} {self.value('device.model', '?')}",
            "facts": len(facts),
            "unknown": [k for k, v in facts if v.get("status") == "unknown"],
        }


def validate(data: dict, path: Path) -> list[str]:
    problems = []
    if data.get("schema") != 1:
        problems.append("schema must be 1")
    if not data.get("id"):
        problems.append("missing id")

    def walk(prefix: str, node: dict) -> None:
        for k, v in node.items():
            if isinstance(v, dict):
                if "status" in v or "value" in v:
                    if v.get("status") not in STATUSES:
                        problems.append(f"{prefix}{k}: status must be one of {sorted(STATUSES)}")
                    if v.get("status") != "unknown" and not v.get("source"):
                        problems.append(f"{prefix}{k}: non-unknown fact requires a source")
                    if v.get("status") == "unknown" and v.get("value") not in (None, "", [], {}):
                        problems.append(f"{prefix}{k}: unknown fact must not carry a value")
                else:
                    walk(f"{prefix}{k}.", v)
    walk("", {k: v for k, v in data.items() if k not in ("schema", "id")})
    return problems


def load_profile(path: Path) -> Profile:
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ProfileError(f"{path}: {e}") from e
    problems = validate(data, Path(path))
    if problems:
        raise ProfileError(f"{path}: " + "; ".join(problems))
    return Profile(id=data["id"], data=data, path=Path(path))


def list_profiles(dirs: list[Path]) -> list[Profile]:
    seen: dict[str, Profile] = {}
    for d in dirs:
        for p in sorted(Path(d).glob("*.toml")) if Path(d).is_dir() else []:
            if p.name.startswith("_"):
                continue
            prof = load_profile(p)
            seen.setdefault(prof.id, prof)
    return list(seen.values())


def get_profile(target: str, dirs: list[Path]) -> Profile:
    for prof in list_profiles(dirs):
        if prof.id == target:
            return prof
    known = ", ".join(p.id for p in list_profiles(dirs)) or "none"
    raise ProfileError(f"unknown device profile '{target}' (available: {known})")
