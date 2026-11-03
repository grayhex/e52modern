"""Documented python-gammu API, isolated in a timeout-bounded worker.

No protocol implementation. Raw phone data travels over private stdin/stdout only.
The Gammu library debug log is disabled before connecting.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime

MAX_RECORDS = 5000
DOMAINS = {
    "contacts": ("GetNextMemory", {"Type": "ME"}, "GetMemoryStatus", {"Type": "ME"}),
    "calendar": ("GetNextCalendar", {}, "GetCalendarStatus", {}),
    "tasks": ("GetNextToDo", {}, "GetToDoStatus", {}),
    "sms": ("GetNextSMS", {"Folder": 0}, "GetSMSStatus", {}),
}


def encode(value):
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, bytes):
        return {"__bytes__": base64.b64encode(value).decode()}
    raise TypeError("Unsupported phone data type")


def decode(value):
    if set(value) == {"__datetime__"}:
        return datetime.fromisoformat(value["__datetime__"])
    if set(value) == {"__bytes__"}:
        return base64.b64decode(value["__bytes__"], validate=True)
    return value


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, default=encode, sort_keys=True).encode()).hexdigest()


def available() -> bool:
    return importlib.util.find_spec("gammu") is not None


def invoke(config: str, action: str, **values) -> dict:
    if not available():
        raise ValueError(
            "python-gammu is not installed on the PC Bridge. Use a Nokia Suite export, or install SymPort with the phone extra"
        )
    try:
        result = subprocess.run(
            [sys.executable, "-m", __name__],
            input=json.dumps(dict(values, config=config, action=action), default=encode),
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if result.returncode or len(result.stdout) > 32 * 1024 * 1024:
            raise ValueError(
                "Gammu connection failed; reconnect and read the phone before retrying"
            )
        data = json.loads(result.stdout, object_hook=decode)
        if data.get("error"):
            raise ValueError(data["error"])
        return data
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ValueError(
            "Gammu did not complete the operation. Read the phone again before retrying a write"
        ) from exc


def error_code(exc) -> str:
    name = type(exc).__name__
    return name if re.fullmatch("ERR_[A-Z_]+", name) else "ERR_CONNECTION"


def read_records(sm, domain: str) -> list[dict]:
    method, args, status_method, status_args = DOMAINS[domain]
    # A successful explicit zero count proves an empty store. ERR_EMPTY alone
    # cannot distinguish an unsupported service from a genuinely empty store.
    status = getattr(sm, status_method)(**status_args)
    count = (
        status.get("Used")
        if domain != "sms"
        else sum(status.get(k, 0) for k in ("SIMUsed", "PhoneUsed", "TemplatesUsed"))
    )
    if domain == "sms" and not any(k in status for k in ("SIMUsed", "PhoneUsed", "TemplatesUsed")):
        raise ValueError("SMS count is unavailable")
    if count == 0:
        return []
    result, seen, location = [], set(), None
    while True:
        try:
            value = getattr(sm, method)(
                **args, **({"Start": True} if location is None else {"Location": location})
            )
        except Exception as exc:
            if (
                error_code(exc) == "ERR_EMPTY"
                and result
                and (count is None or len(result) >= count)
            ):
                return result
            raise
        records = value if isinstance(value, list) else [value]
        if not records:
            raise ValueError("Empty iteration response")
        last = records[-1].get("Location")
        if last is None or last in seen or len(result) + len(records) > MAX_RECORDS:
            raise ValueError("Phone data exceeds the safe read limit or iteration did not advance")
        seen.add(last)
        result.extend(records)
        location = last


def identity(sm) -> dict:
    def optional(method):
        try:
            return getattr(sm, method)()
        except Exception:
            return None

    model, firmware, imei = optional("GetModel"), optional("GetFirmware"), optional("GetIMEI")
    battery, signal, fs = (
        optional("GetBatteryCharge"),
        optional("GetSignalQuality"),
        optional("GetFileSystemStatus"),
    )
    model = " / ".join(str(v) for v in model if v) if isinstance(model, (list, tuple)) else model
    firmware = firmware[0] if isinstance(firmware, (tuple, list)) and firmware else firmware
    rm = re.search(r"RM-\d+", model or "")

    def percent(value):
        return value if isinstance(value, (int, float)) and 0 <= value <= 100 else None

    return {
        "model": model,
        "firmware": firmware,
        "rm": rm.group() if rm else None,
        "battery": percent((battery or {}).get("BatteryPercent")),
        "signal": percent((signal or {}).get("SignalPercent")),
        "free": (fs or {}).get("Free"),
        "total": None,
        "storage_scope": "gammu-filesystem",
        "imei": ("•" * max(0, len(imei) - 4) + imei[-4:]) if isinstance(imei, str) else None,
        "fingerprint": digest([model, firmware, imei]),
        "write_identity": bool(isinstance(imei, str) and re.fullmatch(r"[0-9]{14,17}", imei)),
        "usb_mode": None,
    }


def sms_verified(sm, current: dict) -> bool:
    proof_path = os.getenv("SYMPORT_VERIFIED_SMS_PROFILE")
    if not proof_path:
        return False
    try:
        with open(proof_path, encoding="utf-8") as source:
            proof = json.load(source)
        return (
            proof.get("fingerprint") == current["fingerprint"]
            and proof.get("connection") == sm.GetConfig(0).get("Connection")
            and proof.get("sms_send_verified") is True
        )
    except (OSError, ValueError, AttributeError):
        return False


def execute(sm, data: dict) -> dict:
    action = data["action"]
    if action == "details":
        result = identity(sm)
        result["sms_send_verified"] = sms_verified(sm, result)
        try:
            result["connection"] = sm.GetConfig(0).get("Connection")
        except Exception:
            result["connection"] = None
        result["capability_status"] = {}
        for domain, (_, _, method, args) in DOMAINS.items():
            try:
                getattr(sm, method)(**args)
                result["capability_status"][domain] = {
                    "status": "available",
                    "reason": "Gammu storage status returned successfully",
                }
            except Exception as exc:
                result["capability_status"][domain] = {
                    "status": "unavailable",
                    "reason": error_code(exc),
                }
        return result
    if action == "imei":
        if data.get("confirm") is not True:
            raise ValueError("Confirm revealing the private device identifier")
        return {"imei": sm.GetIMEI()}
    domain = data.get("domain")
    if domain not in DOMAINS:
        raise ValueError("Unknown personal data store")
    current = identity(sm)
    if action == "read":
        return {"identity": current, "records": read_records(sm, domain)}
    if (
        data.get("confirm") is not True
        or data.get("fingerprint") != current["fingerprint"]
        or not current["write_identity"]
    ):
        raise ValueError("Phone identity changed; read it again")
    if action == "write" and domain != "sms":
        record = data["record"]
        method = {"contacts": "Memory", "calendar": "Calendar", "tasks": "ToDo"}[domain]
        location = record.get("Location")
        if location:
            before = getattr(sm, "Get" + method)(
                **(
                    {"Type": "ME", "Location": location}
                    if domain == "contacts"
                    else {"Location": location}
                )
            )
            if digest(before) != data.get("before_hash"):
                raise ValueError("Record changed on the phone; preview again")
            getattr(sm, "Set" + method)(record)
        else:
            location = getattr(sm, "Add" + method)(record)
        after = getattr(sm, "Get" + method)(
            **(
                {"Type": "ME", "Location": location}
                if domain == "contacts"
                else {"Location": location}
            )
        )
        return {"record": after, "location": location}
    if action == "send" and domain == "sms":
        # Operator-enrolled exact device/driver validation, never enabled by a UI checkbox.
        if not sms_verified(sm, current):
            raise ValueError(
                "SMS sending requires an operator-verified profile for this phone and connection"
            )
        number, text = data.get("number"), data.get("text")
        if (
            not isinstance(number, str)
            or not re.fullmatch(r"\+?[0-9]{3,20}", number)
            or not isinstance(text, str)
            or not 1 <= len(text.encode("utf-16-be")) // 2 <= 70
        ):
            raise ValueError("Use a valid phone number and one SMS of at most 70 UTF-16 units")
        reference = sm.SendSMS(
            {
                "Number": number,
                "Text": text,
                "SMSC": {"Location": 1},
                "Coding": "Unicode_No_Compression",
            }
        )
        return {"status": "submitted-to-network", "reference": reference, "delivery": "unknown"}
    raise ValueError("Unsupported personal data operation")


def main():
    sm = None
    try:
        import gammu

        data = json.loads(sys.stdin.read(32 * 1024 * 1024), object_hook=decode)
        gammu.SetDebugLevel("nothing")
        sm = gammu.StateMachine()
        sm.ReadConfig(Filename=data["config"])
        sm.SetDebugLevel("nothing")
        sm.Init()
        result = execute(sm, data)
    except Exception as exc:
        code = error_code(exc)
        result = {
            "error": f"Gammu: {code}. The selected driver cannot complete this request. Use a Nokia Suite export or another configured connection"
        }
    finally:
        if sm is not None:
            try:
                sm.Terminate()
            except Exception:
                pass
    print(json.dumps(result, default=encode))


if __name__ == "__main__":
    main()
