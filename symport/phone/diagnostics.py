"""Explicit device measurements; no inferred telemetry or persistent phone identifiers."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import secrets
from datetime import UTC, datetime

from symport.catalog.service import save

NUMERIC = {
    "battery": (0, 100),
    "signal": (0, 100),
    "free": (0, 2**63),
    "total": (0, 2**63),
    "life_timer_hours": (0, 10**9),
}
FIELDS = ("model", "rm", "firmware", "transport", "connection_kind", "usb_mode")


class DeviceDiagnostics:
    def __init__(self, repo, manager):
        self.root = repo / "build" / "symport" / "diagnostics"
        self.manager = manager
        import threading

        self.lock = threading.RLock()

    def path(self, device):
        if not isinstance(device, str) or not 0 < len(device) <= 200:
            raise ValueError("Choose an enrolled connection")
        return self.root / (hashlib.sha256(device.encode()).hexdigest() + ".json")

    def read(self, device):
        path = self.path(device)
        return (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"measurements": []}
        )

    def execute(self, data):
        with self.lock:
            return self._execute(data)

    def _execute(self, data):
        action, device = data.get("action"), data.get("device")
        self.path(device)
        if action == "clear":
            if data.get("confirm") is not True:
                raise ValueError("Confirm deleting this diagnostic history")
            self.path(device).unlink(missing_ok=True)
            return {"deleted": True}
        history = self.read(device)
        if action == "sample":
            discovered = self.manager.execute({"action": "discover"})
            observed = next((d for d in discovered["devices"] if d["id"] == device), None)
            if not observed:
                raise ValueError("Connection not found. Discover the phone again.")
            # Identity details are requested only from the selected adapter. A failure
            # leaves nulls and an explicit reason; values from previous samples are never reused.
            details, reasons = {}, []
            if observed.get("connected") and "device-details" in observed.get("capabilities", []):
                try:
                    details = self.manager.execute({"action": "device-details", "device": device})
                    if not isinstance(details, dict):
                        details = {}
                except (ValueError, OSError):
                    # Exception text may contain identifiers: persist only a fixed explanation.
                    reasons.append(
                        "Adapter detail read failed; only discovery values are available"
                    )
            source = {**observed, **{k: v for k, v in details.items() if v is not None}}
            measured = {
                "id": secrets.token_hex(12),
                "time": datetime.now(UTC).isoformat(),
                "connected": bool(observed.get("connected")),
                "identity_evidence": "adapter observation",
                "profile": observed.get("model_profile"),
                "capabilities": observed.get("capabilities", []),
                "capability_status": {},
                "reasons": reasons,
            }
            for name in FIELDS:
                value = source.get(name)
                measured[name] = (
                    value[:160]
                    if isinstance(value, str)
                    and value.strip()
                    and value.lower() not in ("unknown", "unavailable")
                    else None
                )
            for name, (low, high) in NUMERIC.items():
                value = source.get(name)
                measured[name] = (
                    value
                    if type(value) in (int, float) and math.isfinite(value) and low <= value <= high
                    else None
                )
            for domain, status in observed.get("capability_status", {}).items():
                if domain in ("contacts", "sms", "calendar", "tasks") and isinstance(status, dict):
                    measured["capability_status"][domain] = {
                        "status": status.get("status", "unknown")
                    }
            if (
                measured["total"] is not None
                and measured["free"] is not None
                and measured["free"] > measured["total"]
            ):
                measured["free"] = None
                measured["reasons"].append("Adapter reported inconsistent free/total memory")
            # No IMEI, phone number, host path, messages, contacts or raw exception/log output.
            previous = history["measurements"][-1] if history["measurements"] else None
            if previous and any(
                previous.get(k) and measured.get(k) and previous[k] != measured[k]
                for k in ("model", "rm")
            ):
                measured["reasons"].append(
                    "Model/RM changed on this connection; this is a separate measurement series"
                )
            measured["series"] = hashlib.sha256(
                json.dumps(
                    [measured.get(k) for k in ("model", "rm", "firmware", "transport")]
                ).encode()
            ).hexdigest()[:16]
            history["measurements"] = [*history["measurements"][-499:], measured]
            save(self.path(device), history)
            self.manager.record("diagnostic-sample", "success")
            return {"sample": measured, **history}
        if action == "history":
            return history
        if action != "export":
            raise ValueError("Unknown diagnostic operation")
        import base64

        if data.get("format", "json") == "json":
            raw = json.dumps(
                {"schema": "symport.diagnostics/1", **history}, ensure_ascii=False, indent=2
            ).encode()
            return {
                "name": "symport-diagnostics.json",
                "mime": "application/json",
                "content": base64.b64encode(raw).decode(),
            }
        if data.get("format") != "csv":
            raise ValueError("Choose JSON or CSV")
        stream = io.StringIO(newline="")
        columns = ["time", "series", "connected", *FIELDS, *NUMERIC]
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in history["measurements"]:
            writer.writerow(
                {
                    k: (
                        "'" + v
                        if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                        else v
                    )
                    for k, v in row.items()
                }
            )
        return {
            "name": "symport-diagnostics.csv",
            "mime": "text/csv",
            "content": base64.b64encode(stream.getvalue().encode()).decode(),
        }
