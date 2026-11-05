"""Per-connection capability matrix: the single source of truth for what a connection can do.

A *capability* is one operation on one connection (``files.list``, ``contacts.read``,
``sms.send`` …), never a property of the phone model. Each entry records

* ``status``: ``available`` (a safe probe of this adapter succeeded), ``not-tested``
  (nothing has proven it yet), ``unsupported`` (the transport cannot do it) or ``error``
  (the probe failed; ``evidence`` carries a fixed reason),
* ``attempt``: whether the operation may still be *tried* — ``verified`` (available),
  ``unverified`` (a read that has not been probed), ``confirmed-only`` (a write that is
  never probed and runs only after an explicit confirmation) or ``blocked``,
* ``source`` / ``evidence`` / ``checked_at``: where the knowledge comes from and when.

Reading never implies writing. Write operations are never probed (no test writes, no SMS):
they become ``available`` only after a confirmed, read-back-verified operation completed on
the *same* connection fingerprint (see :class:`ObservedWrites`).

The flat ``capabilities`` list and the ``capability_status`` map are *derived* from the matrix
for older clients; adapters must not write them by hand. The flat list names only verified
operations and confirmed-only writes; an unprobed read (``unverified``) is offered by clients
that read the matrix, because the read itself is the probe.
"""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime

STATUSES = ("available", "not-tested", "unsupported", "error")

# operation -> (mode, flat names exposed to older clients while the operation may be attempted)
OPERATIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "identity.read": ("read", ("device-details",)),
    "telemetry.read": ("read", ()),
    "storage.read": ("read", ()),
    "files.list": ("read", ("files", "files-list")),
    "files.download": ("read", ("files-download",)),
    "files.upload": ("write", ("files-upload",)),
    "files.stage": ("write", ("files-stage",)),
    "files.mkdir": ("write", ("files-mkdir",)),
    "files.delete": ("write", ("files-delete",)),
    "media.read": ("read", ("media-read",)),
    "packages.transfer": ("write", ("transfer",)),
    "packages.opp-push": ("write", ("opp-push", "transfer")),
    "contacts.read": ("read", ("contacts-read",)),
    "contacts.write": ("write", ("contacts-write",)),
    "contacts.stage": ("write", ("contacts-stage",)),
    "calendar.read": ("read", ("calendar-read",)),
    "tasks.read": ("read", ("tasks-read",)),
    "sms.read": ("read", ("sms-read",)),
    "sms.send": ("write", ("sms-send",)),
    "apps.registry": ("read", ()),
    "install.run": ("write", ()),
}
PIM_READS = ("contacts.read", "calendar.read", "tasks.read", "sms.read")
# Legacy ``capability_status`` domains → matrix operation.
LEGACY_DOMAINS = {
    "contacts": "contacts.read",
    "calendar": "calendar.read",
    "tasks": "tasks.read",
    "sms": "sms.read",
}
# A confirmed, successfully verified action that proves a write operation on this connection.
ACTION_PROOFS = {
    "upload": "files.upload",
    "mkdir": "files.mkdir",
    "delete": "files.delete",
    "software-transfer": "packages.transfer",
    "transfer": "packages.transfer",
    "contacts-stage": "contacts.stage",
}
# Results that prove nothing about the write itself.
UNVERIFIED_RESULTS = (
    "partial-or-unverified",
    "submitted-to-network",
    "received-by-opp-not-installed",
)
INSTALL_REASON = (
    "SymPort never installs software. Copying a package proves nothing about installation; "
    "confirm it on the phone screen."
)
IDENTITY_FIELDS = ("id", "transport", "connection_kind", "manufacturer", "model", "rm", "firmware", "usb_mode", "connection_identity")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def fingerprint(row: dict) -> str:
    """Stable id of *this* connection to *this* phone; changes with model, firmware or link.

    No IMEI/serial is used so it can appear in reports; a different phone of the same model on
    the same profile is distinguished by the user switching connection, not by this value.
    """
    parts = [str(row.get(name) or "") for name in IDENTITY_FIELDS]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


class Matrix:
    """Builder used by adapters; every operation defaults to *not-tested, blocked*."""

    def __init__(self, checked_at: str | None = None):
        self.checked_at = checked_at or now()
        self.entries: dict[str, dict] = {}

    def _put(self, op, status, source, evidence, attempt):
        if op not in OPERATIONS:
            raise KeyError(op)
        self.entries[op] = {
            "mode": OPERATIONS[op][0],
            "status": status,
            "attempt": attempt,
            "source": source,
            "evidence": evidence,
            "checked_at": self.checked_at,
        }
        return self

    def available(self, op, source, evidence):
        return self._put(op, "available", source, evidence, "verified")

    def untested(self, op, source, evidence, attemptable=True):
        mode = OPERATIONS[op][0]
        attempt = (
            ("confirmed-only" if mode == "write" else "unverified") if attemptable else "blocked"
        )
        return self._put(op, "not-tested", source, evidence, attempt)

    def unsupported(self, op, source, evidence):
        return self._put(op, "unsupported", source, evidence, "blocked")

    def error(self, op, source, evidence):
        return self._put(op, "error", source, evidence, "blocked")

    def rest(self, status, source, evidence, ops=None):
        """Fill every operation not set yet with one state."""
        fill = {
            "not-tested": lambda op: self.untested(op, source, evidence, attemptable=False),
            "unsupported": lambda op: self.unsupported(op, source, evidence),
            "error": lambda op: self.error(op, source, evidence),
        }[status]
        for op in ops or OPERATIONS:
            if op not in self.entries:
                fill(op)
        return self

    def finish(self) -> dict:
        """Complete the matrix: SymPort never installs or reads the application registry."""
        self.rest(
            "unsupported",
            "symport-policy",
            "No transport exposes this operation",
            ops=("apps.registry",),
        )
        if "install.run" not in self.entries:
            self.unsupported("install.run", "symport-policy", INSTALL_REASON)
        self.rest("not-tested", "no-probe", "This connection has not been probed for this operation")
        return self.entries


def flat(matrix: dict) -> list[str]:
    names: list[str] = []
    for op, state in matrix.items():
        if state.get("attempt") in ("verified", "confirmed-only"):
            names += [n for n in OPERATIONS.get(op, ("", ()))[1] if n not in names]
    if any(matrix.get(op, {}).get("status") == "available" for op in PIM_READS):
        names.append("personal-data")
    return names


def legacy_status(matrix: dict) -> dict:
    out = {}
    for domain, op in LEGACY_DOMAINS.items():
        state = matrix.get(op)
        if not state:
            continue
        status = {"available": "available", "not-tested": "unknown"}.get(
            state["status"], "unavailable"
        )
        out[domain] = {"status": status, "reason": state["evidence"]}
    return out


def apply(row: dict, matrix: Matrix | dict) -> dict:
    """Attach the matrix to a device row and derive the legacy fields from it."""
    entries = matrix.finish() if isinstance(matrix, Matrix) else matrix
    row["capability_matrix"] = entries
    row["capabilities"] = flat(entries)
    row["capability_status"] = legacy_status(entries)
    row["capability_fingerprint"] = fingerprint(row)
    row["capabilities_checked_at"] = max(
        (s["checked_at"] for s in entries.values() if s.get("checked_at")), default=now()
    )
    return row


def unprobed(row: dict, reason: str) -> dict:
    """Rows from a peer that predates the matrix: nothing is trusted, nothing is invented."""
    matrix = Matrix()
    matrix.rest("not-tested", "unverified-peer-report", reason)
    return apply(row, matrix)


def sanitize(entries) -> dict | None:
    """Validate a matrix received from a bridge; unknown operations/statuses are dropped."""
    if not isinstance(entries, dict):
        return None
    clean = {}
    for op, state in entries.items():
        if op not in OPERATIONS or not isinstance(state, dict) or state.get("status") not in STATUSES:
            continue
        attempt = state.get("attempt")
        if attempt not in ("verified", "confirmed-only", "unverified", "blocked"):
            attempt = "blocked"
        if state["status"] == "available":
            attempt = "verified"
        elif state["status"] in ("unsupported", "error"):
            attempt = "blocked"
        clean[op] = {
            "mode": OPERATIONS[op][0],
            "status": state["status"],
            "attempt": attempt,
            "source": str(state.get("source") or "")[:80],
            "evidence": str(state.get("evidence") or "")[:300],
            "checked_at": str(state.get("checked_at") or "")[:40],
        }
    return clean or None


def finalize(row: dict) -> dict:
    """Idempotent normalisation of a device row coming from any transport or bridge."""
    entries = sanitize(row.get("capability_matrix"))
    if entries is None:
        return unprobed(
            row,
            "The reporting component predates capability probing; update the Windows Bridge",
        )
    for op in OPERATIONS:
        if op not in entries:
            entries[op] = {
                "mode": OPERATIONS[op][0],
                "status": "not-tested",
                "attempt": "blocked",
                "source": "no-probe",
                "evidence": "Not reported by the connection",
                "checked_at": row.get("capabilities_checked_at") or now(),
            }
    return apply(row, entries)


class ObservedWrites:
    """Write proofs from confirmed, read-back-verified operations on one connection fingerprint.

    Memory only. A proof is dropped when the connection disappears or its fingerprint changes
    (other phone, profile, transport or firmware). Failures prove nothing and are not recorded.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.proofs: dict[str, dict] = {}

    def record(self, device_row: dict | None, action: str, result: dict) -> None:
        op = ACTION_PROOFS.get(action)
        if not op or not device_row or not device_row.get("connected"):
            return
        if result.get("status") in UNVERIFIED_RESULTS:
            return
        with self.lock:
            entry = self.proofs.setdefault(
                str(device_row["id"]),
                {"fingerprint": device_row.get("capability_fingerprint"), "ops": {}},
            )
            if entry["fingerprint"] != device_row.get("capability_fingerprint"):
                entry.update(fingerprint=device_row.get("capability_fingerprint"), ops={})
            entry["ops"][op] = now()

    def overlay(self, row: dict) -> dict:
        with self.lock:
            entry = self.proofs.get(str(row.get("id")))
            if entry and (
                not row.get("connected")
                or entry["fingerprint"] != row.get("capability_fingerprint")
            ):
                del self.proofs[str(row.get("id"))]
                entry = None
            if not entry:
                return row
            ops = dict(entry["ops"])
        matrix = row["capability_matrix"]
        for op, when in ops.items():
            state = matrix.get(op)
            if state and state["status"] == "not-tested" and state["attempt"] != "blocked":
                matrix[op] = {
                    **state,
                    "status": "available",
                    "attempt": "verified",
                    "source": "observed-operation",
                    "evidence": "A confirmed operation completed and was verified on this connection",
                    "checked_at": when,
                }
        return apply(row, matrix)
