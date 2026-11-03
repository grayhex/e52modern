"""Aggregate saved JSON reports into a compatibility matrix with explicit evidence levels."""
from __future__ import annotations

import json
from pathlib import Path


def load_reports(directory: Path) -> list[dict]:
    out = []
    for p in sorted(Path(directory).glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("schema", "").startswith("symport.report/"):
            d["_file"] = p.name
            out.append(d)
    return out


def build(reports: list[dict]) -> list[dict]:
    rows = []
    for d in reports:
        comp = d.get("data", {}).get("compatibility", {})
        v = d.get("verification", {})
        rows.append({
            "report": d["_file"], "command": d["command"], "status": d["status"],
            "target": comp.get("target", "-"), "static_verdict": comp.get("status", "-"),
            "static_automated": v.get("static_automated", False),
            "emulator": v.get("emulator", "not-tested"),
            "physical_device": v.get("physical_device", "not-tested"),
        })
    return rows


def to_markdown(rows: list[dict]) -> str:
    head = "| report | command | status | target | static verdict | emulator | physical device |\n|---|---|---|---|---|---|---|\n"
    return head + "\n".join(
        f"| {r['report']} | {r['command']} | {r['status']} | {r['target']} | {r['static_verdict']} | "
        f"{r['emulator']} | {r['physical_device']} |" for r in rows) + "\n"
