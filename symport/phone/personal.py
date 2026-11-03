"""Private read/export and optimistic, add/update-only synchronization.

Snapshots and plans are short-lived in RAM. Backups precede every confirmed write;
no phone deletes, retries, blind replacements or arbitrary native-entry writes.
"""

from __future__ import annotations

import base64
import copy
import csv
import io
import json
import os
import secrets
import time
from datetime import date, datetime
from pathlib import Path

import vobject

from . import gammu_native as native
from .contacts import normalize, signature, vcards

TTL = 900


def fields(record: dict) -> dict:
    return {entry["Type"]: entry.get("Value") for entry in record.get("Entries", [])}


def text(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value or "")


def public(record: dict, domain: str) -> dict:
    f = fields(record)
    identifier = f"{domain}:{record.get('MemoryType', '')}:{record.get('Location')}"
    if domain == "contacts":
        name = (
            f.get("Text_Name")
            or " ".join(str(f.get(k) or "") for k in ("Text_FirstName", "Text_LastName")).strip()
        )
        return {
            "native_id": identifier,
            "name": name,
            "given": f.get("Text_FirstName", ""),
            "family": f.get("Text_LastName", ""),
            "phones": [
                str(e["Value"])
                for e in record.get("Entries", [])
                if e["Type"].startswith("Number_")
            ],
            "emails": [
                str(e["Value"])
                for e in record.get("Entries", [])
                if e["Type"] in ("Text_Email", "Text_Email2")
            ],
        }
    if domain == "sms":
        return {
            "native_id": identifier + f":{record.get('Folder', 0)}",
            "number": str(record.get("Number") or ""),
            "text": str(record.get("Text") or ""),
            "date": text(record.get("DateTime")),
            "state": record.get("State") or "unknown",
            "folder": record.get("Folder"),
            "direction": "incoming"
            if record.get("Type") == "Deliver"
            else "outgoing"
            if record.get("Type") == "Submit"
            else "unknown",
            "part": (record.get("UDH") or {}).get("PartNumber"),
            "parts": (record.get("UDH") or {}).get("AllParts"),
        }
    return {
        "native_id": identifier,
        "uid": str(f.get("LUID") or identifier),
        "kind": domain,
        "summary": str(f.get("TEXT") or ""),
        "description": str(f.get("DESCRIPTION") or ""),
        "location": str(f.get("LOCATION") or ""),
        "start": text(f.get("START_DATETIME")),
        "end": text(f.get("END_DATETIME")) if domain == "calendar" else "",
        "due": text(f.get("END_DATETIME")) if domain == "tasks" else "",
        "completed": bool(f["COMPLETED"]) if "COMPLETED" in f else None,
        "priority": record.get("Priority", "None") if domain == "tasks" else None,
        "recurrence": any(k.startswith("REPEAT_") for k in f),
    }


def unchanged(a: dict, b: dict) -> bool:
    return a["identity"]["fingerprint"] == b["identity"]["fingerprint"] and native.digest(
        a["records"]
    ) == native.digest(b["records"])


def calendar_import(raw: str) -> list[dict]:
    if not isinstance(raw, str) or len(raw.encode()) > 4 * 1024 * 1024:
        raise ValueError("Choose an iCalendar file up to 4 MiB")
    from .gammu_calendar import _text, _when

    rows = []
    try:
        for cal in vobject.readComponents(raw):
            for c in cal.components():
                if c.name not in ("VEVENT", "VTODO"):
                    continue
                if len(rows) >= 500:
                    raise ValueError("Import is limited to 500 entries")
                complex_fields = set(c.contents) - {
                    "uid",
                    "summary",
                    "description",
                    "location",
                    "dtstart",
                    "dtend",
                    "due",
                    "status",
                    "dtstamp",
                    "created",
                    "last-modified",
                    "sequence",
                    "prodid",
                    "categories",
                    "priority",
                }
                categories = getattr(c, "categories", None)
                category_values = list(categories.value) if categories else []
                category_map = {
                    "MEETING": "MEETING",
                    "MISCELLANEOUS": "MEMO",
                    "MEMO": "MEMO",
                    "REMINDER": "REMINDER",
                    "CALL": "CALL",
                    "BIRTHDAY": "BIRTHDAY",
                }
                entry_type = (
                    category_map.get(str(category_values[0]).upper())
                    if len(category_values) == 1
                    else None
                )
                if category_values and entry_type is None:
                    complex_fields.add("categories")
                priority = _text(c, "priority")
                if priority and (c.name != "VTODO" or priority not in {str(i) for i in range(10)}):
                    complex_fields.add("priority")
                priority_name = (
                    (
                        "None"
                        if not priority or priority == "0"
                        else "High"
                        if int(priority) <= 3
                        else "Medium"
                        if int(priority) <= 6
                        else "Low"
                    )
                    if priority is None or priority.isdigit()
                    else "None"
                )
                status = _text(c, "status")
                if status and status not in (
                    {"CONFIRMED"}
                    if c.name == "VEVENT"
                    else {"CONFIRMED", "COMPLETED", "NEEDS-ACTION"}
                ):
                    complex_fields.add("status")
                if any(
                    isinstance(getattr(c, name).value, date)
                    and not isinstance(getattr(c, name).value, datetime)
                    for name in ("dtstart", "dtend", "due")
                    if hasattr(c, name)
                ):
                    complex_fields.add("all-day")
                rows.append(
                    {
                        "kind": "calendar" if c.name == "VEVENT" else "tasks",
                        "uid": _text(c, "uid") or "",
                        "summary": _text(c, "summary") or "",
                        "description": _text(c, "description") or "",
                        "location": _text(c, "location") or "",
                        "start": _when(c, "dtstart") or "",
                        "end": _when(c, "dtend") or "",
                        "due": _when(c, "due") or "",
                        "completed": (_text(c, "status") == "COMPLETED")
                        if _text(c, "status")
                        else None,
                        "unsupported": sorted(complex_fields),
                        "entry_type": entry_type,
                        "priority": priority_name,
                    }
                )
    except Exception as exc:
        raise ValueError(
            "Cannot parse iCalendar; use a standard VEVENT/VTODO export without recurrence or invitations"
        ) from exc
    return rows


def update_record(before: dict | None, row: dict, domain: str) -> dict:
    record = (
        copy.deepcopy(before)
        if before
        else (
            {"Location": 0, "MemoryType": "ME", "Entries": []}
            if domain == "contacts"
            else {
                "Location": 0,
                "Type": "MEETING" if domain == "calendar" else "MEMO",
                "Entries": [],
                **({"Priority": "None"} if domain == "tasks" else {}),
            }
        )
    )
    if domain != "contacts" and not before and row.get("entry_type"):
        if row["entry_type"] not in ("MEETING", "MEMO", "REMINDER", "CALL", "BIRTHDAY"):
            raise ValueError("Unsupported calendar entry type")
        record["Type"] = row["entry_type"]
    if domain == "tasks" and "priority" in row:
        if row["priority"] not in ("High", "Medium", "Low", "None"):
            raise ValueError("Unsupported task priority")
        record["Priority"] = row["priority"]
    if domain == "contacts":
        c = normalize([row])[0]
        if not c["name"] or len(c["phones"]) > 20 or len(c["emails"]) > 20:
            raise ValueError("A contact needs a name and at most 20 numbers/emails")
        # Retain existing number labels/field metadata and split names unless renamed.
        entries = record["Entries"]
        name_changed = before is None or public(before, domain)["name"] != c["name"]
        replacement = [{"Type": "Text_Name", "Value": c["name"]}] if name_changed else []
        old_numbers = [e for e in entries if e["Type"].startswith("Number_")]
        old_emails = [e for e in entries if e["Type"] in ("Text_Email", "Text_Email2")]
        for values, old, default in [
            (c["phones"], old_numbers, "Number_General"),
            (c["emails"], old_emails, "Text_Email"),
        ]:
            for i, value in enumerate(values):
                replacement.append(
                    dict(old[i], Value=value) if i < len(old) else {"Type": default, "Value": value}
                )

        def remove(k):
            return (
                k.startswith("Number_")
                or k in ("Text_Email", "Text_Email2")
                or (name_changed and k in ("Text_Name", "Text_FirstName", "Text_LastName"))
            )
    else:
        if row.get("unsupported") or (before and public(before, domain)["recurrence"]):
            raise ValueError(
                "Recurring entries, invitations and advanced calendar fields require manual import on the phone"
            )
        if not isinstance(row.get("summary"), str) or not 1 <= len(row["summary"]) <= 500:
            raise ValueError("Enter a title up to 500 characters")
        replacement = []
        for key, typ in [
            ("summary", "TEXT"),
            ("description", "DESCRIPTION"),
            ("location", "LOCATION"),
            ("start", "START_DATETIME"),
            ("end" if domain == "calendar" else "due", "END_DATETIME"),
        ]:
            value = row.get(key, "")
            if not isinstance(value, str) or len(value) > 4000:
                raise ValueError("Invalid calendar field")
            if value:
                if typ.endswith("DATETIME"):
                    try:
                        value = datetime.fromisoformat(value)
                    except ValueError as exc:
                        raise ValueError(
                            "Use an ISO date/time. Floating times use the phone timezone"
                        ) from exc
                    # Gammu uses handset wall-clock time; do not silently lose TZ information.
                    if value.tzinfo is not None:
                        raise ValueError(
                            "Convert calendar times to the phone timezone before importing; timezone conversion cannot be inferred"
                        )
                replacement.append({"Type": typ, "Value": value})
        if domain == "calendar" and not row.get("start"):
            raise ValueError("An event needs a start date/time")
        if (
            domain == "calendar"
            and row.get("end")
            and datetime.fromisoformat(row["end"]) < datetime.fromisoformat(row["start"])
        ):
            raise ValueError("End must follow the start")
        if domain == "tasks" and row.get("completed") is not None:
            if type(row["completed"]) is not bool:
                raise ValueError("Invalid task completion state")
            replacement.append({"Type": "COMPLETED", "Value": int(row["completed"])})
        if not before and row.get("uid"):
            replacement.append({"Type": "LUID", "Value": str(row["uid"])[:250]})
        keys = {
            t
            for _, t in [
                ("summary", "TEXT"),
                ("description", "DESCRIPTION"),
                ("location", "LOCATION"),
                ("start", "START_DATETIME"),
                ("end", "END_DATETIME"),
            ]
        } | {"COMPLETED"}

        if row.get("completed") is None:
            keys.discard("COMPLETED")

        def remove(k):
            return k in keys

    record["Entries"] = [e for e in record["Entries"] if not remove(e["Type"])] + replacement
    return record


class PersonalWorkspace:
    def __init__(self, repo: Path, invoke=native.invoke):
        self.root = repo / "build/symport/personal-backups"
        self.invoke = invoke
        self.snapshots, self.plans = {}, {}

    def _prune(self):
        now = time.time()
        for cache in (self.snapshots, self.plans):
            for key in list(cache):
                if now - cache[key]["created"] > TTL:
                    del cache[key]
            if len(cache) >= 20:
                del cache[min(cache, key=lambda k: cache[k]["created"])]

    def _snapshot(self, key):
        value = self.snapshots.get(key)
        if value is None or time.time() - value["created"] > TTL:
            raise ValueError("This preview expired. Read the phone again")
        return value

    def _backup(self, snapshot: dict, label="before-sync") -> str:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        key = secrets.token_hex(16)
        with (self.root / (key + ".json")).open("x", encoding="utf-8") as target:
            os.chmod(target.name, 0o600)
            json.dump(
                {
                    "format": "symport-personal-backup-v1",
                    "scope": snapshot["domain"],
                    "created": datetime.now().isoformat(),
                    "purpose": label,
                    "data": snapshot["data"],
                },
                target,
                default=native.encode,
            )
        return key

    def execute(self, config: str, data: dict) -> dict:
        self._prune()
        action = data["action"]
        if action == "device-details":
            return self.invoke(config, "details")
        if action == "device-imei":
            return self.invoke(config, "imei", confirm=data.get("confirm"))
        if action == "personal-read":
            domain = data.get("domain")
            if domain not in native.DOMAINS:
                raise ValueError("Unknown personal data store")
            result = self.invoke(config, "read", domain=domain)
            key = secrets.token_hex(16)
            self.snapshots[key] = {"created": time.time(), "domain": domain, "data": result}
            rows = [dict(public(r, domain), source_snapshot=key) for r in result["records"]]
            duplicates = []
            if domain == "contacts":
                groups = {}
                for i, row in enumerate(rows):
                    groups.setdefault(signature(row), []).append(i)
                duplicates = [indexes for indexes in groups.values() if len(indexes) > 1]
            return {
                "snapshot": key,
                "domain": domain,
                "rows": rows,
                "duplicates": duplicates,
                "fingerprint": result["identity"]["fingerprint"],
                "expires_in": TTL,
            }
        if action == "personal-backup-download":
            key = data.get("backup")
            if (
                not isinstance(key, str)
                or len(key) != 32
                or any(c not in "0123456789abcdef" for c in key)
            ):
                raise ValueError("Invalid backup")
            path = self.root / (key + ".json")
            return {
                "content": base64.b64encode(path.read_bytes()).decode(),
                "name": "symport-personal-backup.json",
            }
        if action == "personal-calendar-import":
            return {"rows": calendar_import(data.get("text"))}
        snapshot = self._snapshot(data.get("snapshot"))
        domain, original = snapshot["domain"], snapshot["data"]
        if action == "personal-backup":
            key = self._backup(snapshot, "user-export")
            return {"backup": key, "scope": domain}
        if action == "personal-export":
            rows = [public(r, domain) for r in original["records"]]
            format = data.get("format", "json")
            if format == "json":
                raw, mime = (
                    json.dumps({"domain": domain, "rows": rows}, ensure_ascii=False, indent=2),
                    "application/json",
                )
            elif format == "csv" and domain == "sms":
                buffer = io.StringIO(newline="")
                writer = csv.DictWriter(
                    buffer,
                    fieldnames=["number", "date", "direction", "state", "text", "part", "parts"],
                    extrasaction="ignore",
                )
                writer.writeheader()
                for row in rows:
                    writer.writerow(
                        {
                            k: (
                                "'" + v
                                if isinstance(v, str)
                                and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                                else v
                            )
                            for k, v in row.items()
                        }
                    )
                raw, mime = buffer.getvalue(), "text/csv"
            elif format == "vcf" and domain == "contacts":
                try:
                    import gammu

                    raw = "".join(gammu.EncodeVCARD(r) for r in original["records"])
                except ImportError:
                    raw = "".join(vcards(rows)) if rows else ""
                mime = "text/vcard"
            elif format == "ics" and domain in ("calendar", "tasks"):
                try:
                    import gammu

                    enc = gammu.EncodeICALENDAR if domain == "calendar" else gammu.EncodeITODO
                    combined = vobject.iCalendar()
                    combined.add("prodid").value = "-//SymPort//Phone Workspace//EN"
                    for record in original["records"]:
                        exported = vobject.readOne(enc(record))
                        f = fields(record)
                        for component in exported.components():
                            if component.name not in ("VEVENT", "VTODO"):
                                continue
                            if hasattr(component, "uid"):
                                component.uid.value = public(record, domain)["uid"]
                            # Gammu's native dates are handset wall times. Retain
                            # floating times instead of incorrectly assigning UTC.
                            for field, name in [
                                ("START_DATETIME", "dtstart"),
                                ("END_DATETIME", "dtend" if domain == "calendar" else "due"),
                            ]:
                                if isinstance(f.get(field), datetime) and hasattr(component, name):
                                    getattr(component, name).value = f[field]
                            if domain == "tasks":
                                # libGammu's encoder can invert High/Low. The
                                # API enum is authoritative; RFC5545 uses 1=high.
                                priority = {"High": 1, "Medium": 5, "Low": 9, "None": 0}[
                                    record.get("Priority", "None")
                                ]
                                if not hasattr(component, "priority"):
                                    component.add("priority")
                                component.priority.value = str(priority)
                                if not hasattr(component, "status"):
                                    component.add("status")
                                if "COMPLETED" in f:
                                    component.status.value = (
                                        "COMPLETED" if f["COMPLETED"] else "NEEDS-ACTION"
                                    )
                                else:
                                    component.contents.pop("status", None)
                            combined.add(component)
                    raw = combined.serialize()
                except ImportError:
                    raise ValueError(
                        "Install python-gammu on the PC Bridge for full iCalendar export"
                    ) from None
                mime = "text/calendar"
            else:
                raise ValueError("Unsupported export format")
            return {
                "content": base64.b64encode(raw.encode("utf-8")).decode(),
                "name": f"symport-{domain}.{format}",
                "mime": mime,
            }
        if action == "personal-preview":
            if domain == "sms":
                raise ValueError("SMS cannot be edited or deleted")
            if not original["identity"].get("write_identity"):
                raise ValueError(
                    "The driver cannot uniquely identify this phone. Export data and import it manually on the phone"
                )
            incoming = data.get("rows")
            if not isinstance(incoming, list) or not 1 <= len(incoming) <= 500:
                raise ValueError("Preview between 1 and 500 selected entries")
            current = self.invoke(config, "read", domain=domain)
            if not unchanged(current, original):
                raise ValueError(
                    "The phone changed after reading. Read it again before synchronizing"
                )
            existing = {public(r, domain)["native_id"]: r for r in original["records"]}
            uids = (
                {public(r, domain).get("uid"): r for r in original["records"]}
                if domain != "contacts"
                else {}
            )
            changes, seen, skipped, conflicts = [], set(), 0, []
            edited = set()
            for row in incoming:
                if not isinstance(row, dict):
                    raise ValueError("Invalid sync entry")
                identifier = row.get("native_id")
                if identifier and row.get("source_snapshot") != data["snapshot"]:
                    raise ValueError(
                        "This edit belongs to another read snapshot. Read the phone again"
                    )
                if identifier and identifier not in existing:
                    raise ValueError("Unknown record identifier; read again")
                if identifier and identifier in edited:
                    raise ValueError("Select each phone record only once")
                if identifier:
                    edited.add(identifier)
                before = existing.get(identifier)
                if not identifier and domain != "contacts" and row.get("uid") in uids:
                    matching = uids[row["uid"]]
                    candidate = update_record(matching, row, domain)
                    if public(candidate, domain) == public(matching, domain):
                        skipped += 1
                    else:
                        conflicts.append(
                            {
                                "summary": row.get("summary"),
                                "reason": "UID already exists. Edit the existing entry explicitly",
                            }
                        )
                    continue
                after = update_record(before, row, domain)
                desired = public(after, domain)
                key = (
                    signature(desired)
                    if domain == "contacts"
                    else native.digest(
                        {k: v for k, v in desired.items() if k not in ("native_id", "uid")}
                    )
                )
                if (
                    domain == "contacts"
                    and not before
                    and any(signature(public(r, domain)) == key for r in original["records"])
                ):
                    skipped += 1
                    continue
                if (not before and key in seen) or (before and public(before, domain) == desired):
                    skipped += 1
                    continue
                seen.add(key)
                changes.append({"before": before, "after": after})
            key = secrets.token_hex(16)
            self.plans[key] = {
                "created": time.time(),
                "snapshot": data["snapshot"],
                "changes": changes,
                "conflicts": conflicts,
                "used": False,
            }
            return {
                "plan": key,
                "dry_run": True,
                "changes": [
                    {
                        "operation": "update" if x["before"] else "add",
                        "before": public(x["before"], domain) if x["before"] else None,
                        "after": public(x["after"], domain),
                    }
                    for x in changes
                ],
                "conflicts": conflicts,
                "skipped": skipped,
                "deletions": 0,
            }
        if action == "personal-apply":
            plan = self.plans.get(data.get("plan"))
            if (
                not plan
                or plan["snapshot"] != data.get("snapshot")
                or plan["used"]
                or plan["conflicts"]
                or time.time() - plan["created"] > TTL
                or data.get("confirm") is not True
            ):
                raise ValueError("Confirm a current, conflict-free sync preview")
            current = self.invoke(config, "read", domain=domain)
            if not unchanged(current, original):
                raise ValueError("The phone changed; read again and preview a new plan")
            backup = self._backup(snapshot)
            plan["used"] = True  # No automatic retry after any write attempt.
            try:
                result = self.invoke(
                    config,
                    "batch",
                    domain=domain,
                    changes=[
                        {"record": change["after"], "before_hash": native.digest(change["before"])}
                        for change in plan["changes"]
                    ],
                    before_store_hash=native.digest(original["records"]),
                    fingerprint=original["identity"]["fingerprint"],
                    confirm=True,
                )
            except (ValueError, OSError):
                result = {
                    "status": "partial-or-unverified",
                    "verified": 0,
                    "requested": len(plan["changes"]),
                }
            result["backup"] = backup
            if result["status"] != "verified-by-readback":
                result["reason"] = (
                    "The driver failed or read-back differed. Read the phone again before another write"
                )
            return result
        if action == "sms-send":
            if snapshot.get("send_attempted"):
                raise ValueError("A send was already attempted. Read SMS again before another send")
            if domain != "sms" or data.get("confirm") is not True:
                raise ValueError("Confirm sending the SMS to this recipient")
            backup = self._backup(snapshot, "before-sms-send")
            snapshot["send_attempted"] = True
            try:
                result = self.invoke(
                    config,
                    "send",
                    domain="sms",
                    fingerprint=original["identity"]["fingerprint"],
                    number=data.get("number"),
                    text=data.get("text"),
                    confirm=True,
                )
            except (ValueError, OSError):
                return {
                    "status": "partial-or-unverified",
                    "backup": backup,
                    "reason": "The send result is unknown. Read the phone before retrying",
                }
            result["backup"] = backup
            try:
                reread = self.invoke(config, "read", domain="sms")
                result["readback"] = "completed"
                before_hashes = {native.digest(old) for old in original["records"]}
                result["stored_copy"] = any(
                    native.digest(r) not in before_hashes
                    and r.get("Text") == data.get("text")
                    and r.get("Number") == data.get("number")
                    and r.get("Type") == "Submit"
                    for r in reread["records"]
                )
            except ValueError:
                result["readback"] = "unavailable"
            return result
        raise ValueError("Unknown personal data operation")
