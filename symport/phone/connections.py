"""Operator-enrolled Nokia/S60 connection profiles; never HTTP-supplied paths/addresses."""

from __future__ import annotations

import json
import re
from pathlib import Path

KINDS = {"gammu-usb", "gammu-bluetooth", "gammu-s60", "gammu-obex", "obexftp", "obex-opp"}


def load_profiles(filename: str | None) -> list[dict]:
    if not filename:
        return []
    source = Path(filename)
    if source.is_symlink() or source.stat().st_size > 64 * 1024:
        raise ValueError("Invalid connection configuration")
    document = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Connection configuration must be a JSON object")
    profiles = document.get("connections")
    if document.get("schema") != 1 or not isinstance(profiles, list) or len(profiles) > 24:
        raise ValueError("Connection configuration requires schema 1 and at most 24 profiles")
    seen = {"gammu"}
    result = []
    for item in profiles:
        if not isinstance(item, dict) or not re.fullmatch(
            r"[a-z][a-z0-9_-]{0,39}", str(item.get("id", ""))
        ):
            raise ValueError("Invalid connection identifier")
        if item["id"] in seen or item.get("kind") not in KINDS:
            raise ValueError("Duplicate or unsupported connection profile")
        seen.add(item["id"])
        if (
            item.get("manufacturer") != "Nokia"
            or item.get("platform") != "S60"
            or item.get("edition") not in ("2nd", "3rd", "5th", "symbian3")
        ):
            raise ValueError(
                "Only explicitly enrolled Nokia S60 2nd/3rd/5th or Symbian^3 profiles are supported"
            )
        name = item.get("name", item["id"])
        if not isinstance(name, str) or not 1 <= len(name) <= 80 or any(ord(c) < 32 for c in name):
            raise ValueError("Invalid connection name")
        row = dict(item, name=name)
        if item["kind"].startswith("gammu-"):
            config = Path(str(item.get("config", "")))
            if not config.is_absolute():
                raise ValueError("Gammu profiles require an operator-owned absolute config path")
            row["config"] = str(config)
        else:
            transport = item.get("transport", "bluetooth")
            if transport == "bluetooth":
                if not re.fullmatch(
                    r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", str(item.get("address", ""))
                ):
                    raise ValueError("Configure a paired Bluetooth address")
                if type(item.get("channel")) is not int or not 1 <= item["channel"] <= 30:
                    raise ValueError("Configure the SDP-reported RFCOMM channel (1–30)")
            elif transport == "usb" and item["kind"] == "obexftp":
                if type(item.get("interface")) is not int or not 0 <= item["interface"] <= 127:
                    raise ValueError("Configure the currently discovered USB OBEX interface")
            else:
                raise ValueError("Only Bluetooth Classic and USB OBEX transports are supported")
            row["transport"] = transport
        result.append(row)
    return result
