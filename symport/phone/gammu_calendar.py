"""Calendar and to-do export through Gammu (read-only).

Uses the documented ``gammu backup <file>.ics`` form: by file extension Gammu writes standard
iCalendar (calendar and to-do). The file is parsed with vobject. Nothing is ever written to the
phone, and an empty export is reported as ambiguous (no calendar vs. no support), never as success.
Not exercised against a physical Nokia E52.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import vobject

from .gammu_contacts import _run

MAX_BYTES = 8 * 1024 * 1024


def _text(component, name: str) -> str | None:
    item = getattr(component, name, None)
    return str(item.value).strip() if item is not None and item.value not in (None, "") else None


def _when(component, name: str) -> str | None:
    item = getattr(component, name, None)
    if item is None:
        return None
    value = item.value
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def parse_ics(raw: bytes) -> dict:
    """Parse an iCalendar export into normalised events and to-dos."""
    if len(raw) > MAX_BYTES:
        raise ValueError("calendar export is larger than 8 MiB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    events, todos, skipped = [], [], 0
    try:
        for cal in vobject.readComponents(text):
            for comp in cal.components():
                kind = comp.name.upper()
                if kind == "VEVENT":
                    events.append({"summary": _text(comp, "summary"), "start": _when(comp, "dtstart"),
                                   "end": _when(comp, "dtend"), "location": _text(comp, "location"),
                                   "description": _text(comp, "description"),
                                   "recurrence": _text(comp, "rrule")})
                elif kind == "VTODO":
                    todos.append({"summary": _text(comp, "summary"), "due": _when(comp, "due"),
                                  "status": _text(comp, "status"), "priority": _text(comp, "priority"),
                                  "description": _text(comp, "description")})
                else:
                    skipped += 1
    except vobject.base.ParseError as e:
        raise ValueError(f"unreadable iCalendar data: {e}") from e
    return {"events": events, "todos": todos, "skipped_components": skipped}


def read(config: str, include_raw: bool = False) -> dict:
    with tempfile.TemporaryDirectory(prefix="symport-calendar-") as tmp:
        path = Path(tmp) / "phone.ics"
        _run(config, ["backup", str(path), "-yes"])
        if not path.exists():
            raise ValueError("Gammu did not create a calendar export")
        raw = path.read_bytes()
        if not raw.strip():
            raise ValueError("Gammu returned an empty calendar export: an empty calendar cannot be "
                             "distinguished from missing support")
        data = parse_ics(raw)
        data["raw_ics_bytes"] = len(raw)
        if include_raw:
            import base64
            data["raw_ics"] = base64.b64encode(raw).decode()
        if not data["events"] and not data["todos"]:
            data["status"] = "empty-or-unsupported"
        else:
            data["status"] = "read"
        return data
