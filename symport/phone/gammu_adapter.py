"""Gammu adapter shared by Linux, configured USB/Bluetooth and Windows Bridge."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from . import capabilities, failure, gammu_native
from .models import documented_model
from .personal import PersonalWorkspace


class GammuAdapter:
    def __init__(self, repo: Path, identifier: str, config, name: str | None = None, kind="gammu"):
        self.id, self.name, self.kind = identifier, name or identifier, kind
        self.config = config if callable(config) else lambda: str(config)
        self.personal = PersonalWorkspace(repo)
        self.scope_error = None
        self.probed = False

    def _matrix(self, device: dict, details: dict | None, identified: bool, native_error: bool):
        """Capabilities of this Gammu connection, from what actually answered.

        ``gammu identify`` proves identity only. PIM stores are readable only after the
        native status call of that store succeeded; writes are never probed.
        """
        m = capabilities.Matrix()
        files = (
            "Gammu S60 file getters are NOTIMPLEMENTED in the audited driver"
            if self.kind == "gammu-s60"
            else "The Gammu adapter exposes no filesystem; use Mass Storage or OBEX FTP"
        )
        for op in ("files.list", "files.download", "files.upload", "files.stage", "files.mkdir",
                   "files.delete", "media.read", "packages.transfer", "packages.opp-push",
                   "contacts.stage"):
            m.unsupported(op, "gammu-profile", files)
        if details is not None:
            m.available("identity.read", "gammu-native:details", "Gammu identity responded")
            telemetry = any(type(details.get(k)) in (int, float) for k in ("battery", "signal"))
            if telemetry:
                m.available("telemetry.read", "gammu-native:details", "Battery or signal value returned")
            else:
                m.unsupported("telemetry.read", "gammu-native:details", "The driver returned no battery or signal value")
            if type(details.get("free")) in (int, float) or type(details.get("total")) in (int, float):
                m.available("storage.read", "gammu-native:GetFileSystemStatus", "Phone filesystem status returned")
            else:
                m.unsupported("storage.read", "gammu-native:details", "The driver returned no storage values")
            status = details.get("capability_status") or {}
            for domain, op in capabilities.LEGACY_DOMAINS.items():
                state = status.get(domain) or {}
                source = "gammu-native:" + gammu_native.DOMAINS[domain][2]
                if state.get("status") == "available":
                    m.available(op, source, "The store status call succeeded (no records were read)")
                elif state.get("status") == "unavailable":
                    code = str(state.get("reason") or "ERR_CONNECTION")
                    if code in ("ERR_NOTSUPPORTED", "ERR_NOTIMPLEMENTED"):
                        m.unsupported(op, source, "Not supported by this driver or phone: " + code)
                    else:
                        m.error(op, source, "Store status failed: " + code)
                else:
                    m.untested(op, source, "The store was not probed", attemptable=False)
            for write, read, source in (
                ("contacts.write", "contacts.read", "read-back-verified apply"),
                ("sms.send", None, "sms-send"),
            ):
                if read and m.entries[read]["status"] != "available":
                    m.untested(write, source, "Needs a readable store for read-back verification", attemptable=False)
                elif read is None and not details.get("sms_send_verified"):
                    m.untested(write, source, "Sending is never probed; no verified-send profile for this phone", attemptable=False)
                else:
                    m.untested(write, source, "Writes are never probed; confirmed apply is verified by read-back")
            if details.get("sms_send_verified") is not True:
                m.entries["sms.send"]["attempt"] = "blocked"
        elif identified:
            why = (
                "python-gammu is not installed; gammu identify does not read any store"
                if not gammu_native.available()
                else "Identity answered but the store probe did not complete; recheck"
            )
            m.available("identity.read", "gammu-cli:identify", "gammu identify answered")
            m.unsupported("telemetry.read", "gammu-cli:identify", "identify returns no battery or signal")
            m.unsupported("storage.read", "gammu-cli:identify", "identify returns no storage values")
            for op in ("contacts.read", "calendar.read", "tasks.read"):
                # `gammu backup` exports exist as a read-only path, but nothing has proven them yet.
                m.untested(
                    op,
                    "gammu-cli:identify",
                    why + "; an explicit read through the CLI export can try it",
                )
            for op in ("sms.read", "contacts.write", "sms.send"):
                m.untested(op, "gammu-cli:identify", why, attemptable=False)
        else:
            reason = (
                "Gammu connection failed; check the configured driver and phone mode"
                if native_error
                else "Gammu unavailable, configuration invalid or phone unreachable"
            )
            m.rest("error", "gammu-connection", reason)
        return m

    def device(self):
        config = self.config()
        if config:
            device = {
                "id": self.id,
                "transport": "gammu",
                "connected": False,
                "model": None,
                "rm": None,
                "firmware": None,
                "battery": None,
                "evidence": "Gammu identification not yet successful",
            }
            details, native_error = None, False
            if gammu_native.available():
                try:
                    details = self.personal.execute(config, {"action": "device-details"})
                    device.update(details, connected=True, evidence="Gammu service responses")
                except ValueError as exc:
                    native_error = True
                    device["failure"] = {"reason": failure.classify(exc)}
                    device["evidence"] = (
                        "Gammu connection failed; check the configured driver and phone mode"
                    )
            if not device["connected"]:
                try:
                    output = subprocess.run(
                        ["gammu", "--config", config, "identify"],
                        capture_output=True,
                        text=True,
                        timeout=20,
                        check=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        env={**os.environ, "LC_ALL": "C"},
                    ).stdout
                    values = {}
                    for line in output.splitlines():
                        key, sep, value = line.partition(":")
                        if sep:
                            values[key.strip().lower()] = value.strip()
                    model = values.get("model")
                    if model:
                        rm = re.search(r"RM-\d+", model)
                        device.update(
                            connected=True,
                            model=model,
                            manufacturer=values.get("manufacturer"),
                            rm=rm.group() if rm else None,
                            firmware=values.get("firmware"),
                            evidence="Gammu CLI identity response only; stores are not read until a native probe succeeds",
                        )
                except FileNotFoundError:
                    if "failure" not in device:
                        device["failure"] = {"reason": "gammu-missing"}
                    device["evidence"] = (
                        "Gammu unavailable, configuration invalid or phone unreachable"
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    # CLI stderr only feeds the classifier; it is never copied into the row.
                    text = getattr(exc, "stderr", "") or ""
                    reason = failure.classify(text)
                    if reason != "unknown" or "failure" not in device:
                        device["failure"] = {"reason": reason}
                    device["evidence"] = (
                        "Gammu unavailable, configuration invalid or phone unreachable"
                    )
            self.probed = True
            platform = documented_model(str(device.get("model") or ""))
            if platform:
                device["platform_info"] = platform
            scope_blocked = (
                self.kind != "gammu"
                and device["connected"]
                and (not platform or str(device.get("manufacturer", "Nokia")).casefold() != "nokia")
            )
            if scope_blocked:
                self.scope_error = (
                    "This connection did not identify a supported Nokia S60 3rd/5th Edition model"
                )
                device.update(
                    connected=False,
                    evidence=self.scope_error,
                    failure={"reason": "unsupported-model"},
                )
            else:
                self.scope_error = None
            device["name"] = self.name
            device["connection_kind"] = self.kind
            # Keep probe details out of the row; the matrix is the single answer.
            for stale in ("capability_status", "capabilities"):
                device.pop(stale, None)
            if scope_blocked:
                matrix = capabilities.Matrix().rest("error", "scope-check", self.scope_error)
            else:
                matrix = self._matrix(device, details, device["connected"], native_error)
            return capabilities.apply(device, matrix)
        return None

    def execute(self, data: dict) -> dict:
        from . import gammu_contacts

        if self.kind != "gammu" and not self.probed:
            self.device()
        if self.scope_error:
            raise ValueError(self.scope_error)
        config = self.config()
        if not config:
            raise ValueError("Настройте Gammu на ПК с телефоном")
        if data["action"].startswith("personal-") or data["action"] in (
            "device-details",
            "device-imei",
            "sms-send",
        ):
            return self.personal.execute(config, data)
        if data["action"] == "contacts-read":
            return {"contacts": gammu_contacts.read(config)}
        if data["action"] == "contacts-import":
            raise ValueError(
                "Use the phone sync preview with python-gammu for direct writes, or transfer vCard files and import them on the phone"
            )
        if data["action"] == "calendar-read":
            from . import gammu_calendar

            return gammu_calendar.read(config, include_raw=True)
        raise ValueError("Gammu предоставляет контакты; для файлов выберите накопитель")
