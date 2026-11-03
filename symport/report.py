"""Structured JSON reports with explicit evidence levels.

Every check carries a *level* so that static file validation is never confused with
firmware, emulator or physical-device evidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "symport.report/1"

# check statuses
PASS, FAIL, WARN, SKIP, UNKNOWN = "pass", "fail", "warn", "skip", "unknown"
# evidence levels
STATIC, ENVIRONMENT, FIRMWARE, EMULATOR, DEVICE = (
    "static", "environment", "firmware", "emulator", "device")

# exit codes
EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_UNSUPPORTED = 0, 1, 2, 3


@dataclass
class Check:
    id: str
    status: str
    message: str
    level: str = STATIC
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"id": self.id, "status": self.status, "level": self.level, "message": self.message}
        if self.evidence:
            d["evidence"] = self.evidence
        return d


@dataclass
class Report:
    command: str
    status: str = "ok"           # ok | failed | unsupported
    checks: list[Check] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    # What kind of verification actually happened. Never inferred from success.
    verification: dict = field(default_factory=lambda: {
        "static_automated": False, "emulator": "not-tested", "physical_device": "not-tested"})

    def add(self, id: str, status: str, message: str, level: str = STATIC, **evidence) -> Check:
        c = Check(id, status, message, level, evidence)
        self.checks.append(c)
        return c

    def unsupported(self, message: str, instructions: list[str] | None = None) -> None:
        self.status = "unsupported"
        self.data["unsupported_reason"] = message
        if instructions:
            self.data["instructions"] = instructions

    def finalize(self) -> Report:
        if self.status == "ok" and any(c.status == FAIL for c in self.checks):
            self.status = "failed"
        return self

    @property
    def exit_code(self) -> int:
        self.finalize()
        return {"ok": EXIT_OK, "failed": EXIT_FAILED, "unsupported": EXIT_UNSUPPORTED}[self.status]

    def to_dict(self) -> dict:
        self.finalize()
        return {
            "schema": SCHEMA, "command": self.command, "status": self.status,
            "verification": self.verification, "checks": [c.to_dict() for c in self.checks],
            "artifacts": self.artifacts, "limitations": self.limitations, "data": self.data,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=False)

    def write(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_json() + "\n", encoding="utf-8")

    def to_text(self) -> str:
        self.finalize()
        mark = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN", SKIP: "SKIP", UNKNOWN: "UNKN"}
        lines = [f"== {self.command}: {self.status.upper()} =="]
        for c in self.checks:
            lines.append(f"  [{mark.get(c.status, c.status)}] ({c.level}) {c.id}: {c.message}")
        if self.status == "unsupported":
            lines.append("  " + str(self.data.get("unsupported_reason", "")))
            for i in self.data.get("instructions", []):
                lines.append("    - " + i)
        for a in self.artifacts:
            lines.append(f"  artifact: {a['path']} ({a['size']} B, sha256 {a['sha256'][:12]}…)")
        if self.limitations:
            lines.append("  Limitations:")
            lines += [f"    - {x}" for x in self.limitations]
        v = self.verification
        lines.append(f"  Verification: static={'yes' if v.get('static_automated') else 'no'}, "
                     f"emulator={v.get('emulator')}, physical device={v.get('physical_device')}")
        return "\n".join(lines)
