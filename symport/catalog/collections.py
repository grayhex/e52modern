"""Portable application selections and preview-bound recovery using curated catalog jobs."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from datetime import UTC, datetime

from .service import save

PROFILES = {
    "nokia-e52": {"model": "Nokia E52", "symbian": "9.3", "s60": "3rd FP2", "screen": [240, 320]},
    "nokia-e72": {"model": "Nokia E72", "symbian": "9.3", "s60": "3rd FP2", "screen": [320, 240]},
}
TEMPLATES = [
    ("basic", "Basic set", "Базовый набор", ["xplore", "opera-mini", "s2putty"]),
    ("internet", "Internet", "Интернет", ["opera-mini", "mpgram", "s2putty"]),
    ("multimedia", "Multimedia", "Мультимедиа", ["fplay", "internet-radio"]),
    ("tools", "Tools", "Инструменты", ["xplore", "fshell", "qremotecontrol", "ip-calculator"]),
]
KEY = re.compile(r"^[a-f0-9]{24}$")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class Collections:
    def __init__(self, service):
        self.service = service
        self.path = service.root / "collections.json"
        self.previews = {}
        legacy = service.root / "sets.json"
        if not self.path.exists() and legacy.exists():
            # Preserve old selections without inventing historical version/hash evidence.
            migrated = {}
            for name, ids in json.loads(legacy.read_text(encoding="utf-8")).items():
                document = self.validate(
                    {
                        "schema": "symport.collection/1",
                        "name": name,
                        "profile": "nokia-e52",
                        "apps": [
                            {"id": key, "version": "legacy-unpinned", "artifacts": []}
                            for key in dict.fromkeys(ids)
                        ],
                    }
                )
                document["updated"] = datetime.now(UTC).isoformat()
                migrated[secrets.token_hex(12)] = document
            save(self.path, migrated)

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def snapshot(self, ids):
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 50
            or any(not isinstance(key, str) for key in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Choose 1–50 distinct applications")
        result = []
        for key in ids:
            entry = self.service.catalog.entries.get(key) if isinstance(key, str) else None
            if not entry:
                raise ValueError("Unknown catalog application")
            source = self.service.catalog.sources.get(entry["source_id"], {})
            result.append(
                {
                    "id": key,
                    "version": entry["version"],
                    "artifacts": [
                        {"name": a["name"], "sha256": a["sha256"], "size": a["size"]}
                        for a in source.get("artifacts", [])
                    ],
                }
            )
        return result

    @staticmethod
    def validate(document):
        if not isinstance(document, dict) or document.get("schema") != "symport.collection/1":
            raise ValueError("Choose a SymPort collection JSON (schema symport.collection/1)")
        if len(json.dumps(document).encode()) > 128 * 1024:
            raise ValueError("Collection exceeds 128 KiB")
        name, profile, apps = document.get("name"), document.get("profile"), document.get("apps")
        if (
            not isinstance(name, str)
            or not 1 <= len(name.strip()) <= 60
            or any(ord(c) < 32 for c in name)
        ):
            raise ValueError("Collection name must be 1–60 printable characters")
        if profile not in PROFILES or not isinstance(apps, list) or not 1 <= len(apps) <= 50:
            raise ValueError("Select an E52/E72 profile and 1–50 applications")
        clean, seen = [], set()
        for app in apps:
            if (
                not isinstance(app, dict)
                or not isinstance(app.get("id"), str)
                or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", app["id"])
                or app["id"] in seen
            ):
                raise ValueError("Invalid or duplicate application ID")
            seen.add(app["id"])
            version, artifacts = app.get("version"), app.get("artifacts", [])
            if (
                not isinstance(version, str)
                or len(version) > 80
                or not isinstance(artifacts, list)
                or len(artifacts) > 8
            ):
                raise ValueError("Invalid version or artifact inventory")
            checked = []
            for artifact in artifacts:
                if (
                    not isinstance(artifact, dict)
                    or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", str(artifact.get("name", "")))
                    or not re.fullmatch(r"[a-f0-9]{64}", str(artifact.get("sha256", "")))
                    or type(artifact.get("size")) is not int
                    or not 0 < artifact["size"] <= 32 * 1024**2
                ):
                    raise ValueError("Invalid artifact hash, filename or size")
                checked.append({k: artifact[k] for k in ("name", "sha256", "size")})
            clean.append({"id": app["id"], "version": version, "artifacts": checked})
        # Imported URLs, commands, device IDs and installation claims are never retained/executed.
        return {
            "schema": "symport.collection/1",
            "name": name.strip(),
            "profile": profile,
            "apps": clean,
        }

    def get(self, key):
        if not isinstance(key, str) or not KEY.fullmatch(key) or key not in self.read():
            raise ValueError("Unknown collection")
        return self.read()[key]

    def plan(self, document, profile, device=""):
        target = PROFILES.get(profile)
        if not target:
            raise ValueError("Choose Nokia E52 or E72")
        catalog = self.service.catalog
        requested = {a["id"]: a for a in document["apps"]}
        ordered, visiting, visited, problems = [], set(), set(), []

        def visit(key):
            if key in visiting:
                raise ValueError("Dependency cycle: " + key)
            if key in visited:
                return
            entry = catalog.entries.get(key)
            visiting.add(key)
            if entry:
                for dependency in entry["dependencies"]:
                    visit(dependency)
            visiting.remove(key)
            visited.add(key)
            ordered.append(key)

        for key in requested:
            visit(key)
        rows, eligible = [], []
        for key in ordered:
            entry = catalog.entries.get(key)
            reasons, status = [], "ready-for-transfer"
            if not entry:
                rows.append(
                    {
                        "id": key,
                        "name": key,
                        "status": "unresolved",
                        "reasons": ["Application is absent from the current curated catalog"],
                        "sources": [],
                        "compatibility": "unknown",
                    }
                )
                continue
            artifacts = self.snapshot([key])[0]["artifacts"]
            pin = requested.get(key)
            if pin and (pin["version"] != entry["version"] or pin["artifacts"] != artifacts):
                reasons.append(
                    "Legacy selection has no original version/hash evidence. Review and re-save before recovery."
                    if pin["version"] == "legacy-unpinned"
                    else "Version or distribution SHA-256 changed. Review and re-save the collection before transferring."
                )
                status = "changed"
            supported = entry.get("target_profiles")
            if (
                supported
                and profile not in supported
                or entry["compatibility"] in ("unsupported", "unavailable")
            ):
                reasons.append("The selected model/platform is unsupported by the catalog evidence")
                status = "unsupported"
            elif entry["category"] == "high-risk":
                status = "unsupported"
                reasons.append("High-risk applications are excluded from recovery batches")
            elif entry["delivery"] == "manual" or not entry["source_id"]:
                reasons.append(
                    entry.get("delivery_reason")
                    or "Obtain your package from the author and transfer it normally"
                )
                status = "manual"
            if any(
                row["id"] in entry["dependencies"] and row["status"] != "ready-for-transfer"
                for row in rows
            ):
                status = "blocked-dependency"
                reasons.append("Resolve the required runtime/application first")
            if status == "ready-for-transfer":
                eligible.append(key)
            rows.append(
                {
                    "id": key,
                    "name": entry["name"],
                    "version": entry["version"],
                    "status": status,
                    "reasons": reasons,
                    "sources": entry["sources"],
                    "compatibility": entry["compatibility"],
                    "artifacts": artifacts,
                    "dependencies": entry["dependencies"],
                    "requirements": entry.get("requirements", []),
                    "runtime_requirements": entry.get("runtime_requirements", []),
                }
            )
        if eligible:
            problems.extend(catalog.plan(eligible, profile)["problems"])
        identity = None
        if device:
            identity = next(
                (
                    d
                    for d in self.service.devices.execute({"action": "discover"})["devices"]
                    if d["id"] == device
                ),
                None,
            )
            if not identity or not identity.get("connected") and not identity.get("configured"):
                problems.append("Select an available phone connection")
            elif "transfer" not in identity.get("capabilities", []):
                problems.append("The connection cannot transfer packages")
            elif identity.get("model_profile") and identity["model_profile"]["id"] != profile:
                problems.append("Selected target differs from the model reported by the adapter")
        result = {
            "collection": document["name"],
            "profile": profile,
            "target": target,
            "source_profile": document["profile"],
            "geometry_changed": profile != document["profile"],
            "rows": rows,
            "transfer_ids": eligible,
            "problems": problems,
            "partial": len(eligible) != len(rows),
            "installation": "not-tested",
            "identity": {k: identity.get(k) for k in ("model", "rm", "firmware", "transport")}
            if identity
            else None,
            "instructions": [
                {
                    "en": "Back up accessible phone data before recovery.",
                    "ru": "До восстановления сохраните копию доступных данных телефона.",
                },
                {
                    "en": "Review model, Symbian version, display geometry, licenses and missing runtimes.",
                    "ru": "Проверьте модель, версию Symbian, экран, лицензии и недостающие runtime.",
                },
                {
                    "en": "Transferred files are not installed applications. Open packages on Nokia in dependency order.",
                    "ru": "Переданные файлы ещё не установлены. Открывайте пакеты на Nokia в порядке зависимостей.",
                },
                {
                    "en": "Restore contacts, SMS and calendar from separate backups; a collection contains no personal data.",
                    "ru": "Контакты, SMS и календарь восстанавливаются из отдельных копий; в наборе нет личных данных.",
                },
            ],
        }
        result["preview_sha256"] = digest({"document": document, "plan": result, "device": device})
        return result

    def execute(self, data):
        action = data["action"]
        if action == "collections":
            templates = []
            for key, en, ru, ids in TEMPLATES:
                templates.append(
                    {
                        "id": key,
                        "en": en,
                        "ru": ru,
                        "ids": [i for i in ids if i in self.service.catalog.entries],
                    }
                )
            return {
                "collections": [{"id": key, **value} for key, value in self.read().items()],
                "templates": templates,
                "profiles": PROFILES,
            }
        if action in ("collection-save", "collection-import"):
            document = (
                self.validate(data.get("document"))
                if action == "collection-import"
                else self.validate(
                    {
                        "schema": "symport.collection/1",
                        "name": data.get("name"),
                        "profile": data.get("profile"),
                        "apps": self.snapshot(
                            self.service.catalog.plan(
                                data.get("ids"), data.get("profile", "nokia-e52")
                            )["ids"]
                        ),
                    }
                )
            )
            values = self.read()
            key = data.get("id") if action == "collection-save" else None
            if key and (not isinstance(key, str) or not KEY.fullmatch(key) or key not in values):
                raise ValueError("Unknown collection")
            if not key and len(values) >= 40:
                raise ValueError("Maximum 40 collections")
            key = key or secrets.token_hex(12)
            document["updated"] = datetime.now(UTC).isoformat()
            values[key] = document
            save(self.path, values)
            return {"id": key, **document}
        document = self.get(data.get("id"))
        if action == "collection-export":
            return self.validate(document)
        if action == "collection-delete":
            if data.get("confirm") is not True:
                raise ValueError("Confirm collection deletion; phone data is unaffected")
            values = self.read()
            del values[data["id"]]
            save(self.path, values)
            return {"deleted": True}
        plan = self.plan(document, data.get("profile", document["profile"]), data.get("device", ""))
        if action == "recovery-plan":
            self.previews = {
                k: v for k, v in self.previews.items() if time.monotonic() - v["created"] < 600
            }
            if len(self.previews) >= 100:
                self.previews.pop(next(iter(self.previews)))
            token = secrets.token_hex(32)
            self.previews[token] = {"digest": plan["preview_sha256"], "created": time.monotonic()}
            return dict(plan, preview_sha256=token)
        if action != "recovery-transfer":
            raise ValueError("Unknown collection operation")
        preview = (
            self.previews.get(data.get("preview_sha256"))
            if isinstance(data.get("preview_sha256"), str)
            else None
        )
        if (
            data.get("confirm") is not True
            or not preview
            or preview["digest"] != plan["preview_sha256"]
            or time.monotonic() - preview["created"] >= 600
        ):
            raise ValueError(
                "Confirm a current recovery preview for this collection, phone and profile"
            )
        if not data.get("device") or plan["problems"] or not plan["transfer_ids"]:
            raise ValueError(
                "Recovery preview has no transferable applications or has connection problems"
            )
        if plan["partial"] and data.get("ack_partial") is not True:
            raise ValueError(
                "Acknowledge the manual/unresolved applications before transferring a partial set"
            )
        self.previews.pop(
            data["preview_sha256"]
        )  # Consume before any uncertain network/device write.
        job = self.service.execute(
            {
                "action": "transfer",
                "ids": plan["transfer_ids"],
                "profile": plan["profile"],
                "device": data["device"],
                "path": data.get("path", ""),
                "confirm": True,
            }
        )
        return {"job": job, "plan": plan, "status": "queued-not-installed"}
