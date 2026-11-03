"""Gammu adapter shared by Linux, configured USB/Bluetooth and Windows Bridge."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from . import gammu_native
from .models import documented_model
from .personal import PersonalWorkspace


class GammuAdapter:
    def __init__(self, repo: Path, identifier: str, config, name: str | None = None, kind="gammu"):
        self.id, self.name, self.kind = identifier, name or identifier, kind
        self.config = config if callable(config) else lambda: str(config)
        self.personal = PersonalWorkspace(repo)
        self.scope_error = None
        self.probed = False

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
                "capabilities": [],
                "evidence": "Gammu identification not yet successful",
            }
            if gammu_native.available():
                try:
                    details = self.personal.execute(config, {"action": "device-details"})
                    device.update(details, connected=True, evidence="Gammu service responses")
                    device["capabilities"] = ["device-details", "personal-data"]
                    device["capabilities"] += [
                        name + "-read"
                        for name, status in details["capability_status"].items()
                        if status["status"] == "available"
                    ]
                except ValueError:
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
                            capabilities=["contacts-read", "calendar-read"],
                            evidence="Gammu CLI identity response; read the selected store to check access",
                        )
                except (OSError, subprocess.SubprocessError):
                    device["evidence"] = (
                        "Gammu unavailable, configuration invalid or phone unreachable"
                    )
            self.probed = True
            platform = documented_model(str(device.get("model") or ""))
            if platform:
                device["platform_info"] = platform
            if (
                self.kind != "gammu"
                and device["connected"]
                and (not platform or str(device.get("manufacturer", "Nokia")).casefold() != "nokia")
            ):
                self.scope_error = (
                    "This connection did not identify a supported Nokia S60 3rd/5th Edition model"
                )
                device.update(connected=False, capabilities=[], evidence=self.scope_error)
            else:
                self.scope_error = None
            device["name"] = self.name
            device["connection_kind"] = self.kind
            return device
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
