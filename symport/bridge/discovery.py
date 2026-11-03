"""Nokia-only host enumeration. No pairing, jailbreak, driver installation or SMS."""

from __future__ import annotations

import json
import os
import re
import subprocess

# Documented device families, not measured firmware/OS facts. Other Nokia devices
# are reported as candidates until explicitly enrolled; S40/other vendors aren't promoted.
from symport.phone.models import documented_model


def serial_candidates():
    try:
        from serial.tools import list_ports
    except ImportError:
        return [], "pyserial is unavailable; configure an existing Gammu connection manually"
    result = []
    for port in list_ports.comports():
        description = " ".join(
            str(x or "") for x in (port.manufacturer, port.description, port.product)
        )
        if port.vid != 0x0421 and "nokia" not in description.casefold():
            continue
        if not isinstance(port.device, str) or not re.fullmatch(
            r"COM[0-9]{1,4}|/dev/[A-Za-z0-9_./-]{1,120}", port.device
        ):
            continue
        result.append(
            {
                "port": port.device,
                "model_profile": documented_model(description),
                "vendor": "Nokia",
                "source": "host-serial-enumeration",
            }
        )
    return result, None


def windows_nokia_volumes():
    if os.name != "nt":
        return [], None
    # CIM associations tie each logical drive to its physical Nokia USB device.
    # Drive letters and Bluetooth names alone are never treated as phone identity.
    script = """$ErrorActionPreference='Stop'; $items=@(); Get-CimInstance Win32_DiskDrive | Where-Object { $_.InterfaceType -eq 'USB' -and ($_.PNPDeviceID -match 'NOKIA|VID_0421' -or $_.Model -match 'Nokia') } | ForEach-Object { $disk=$_; Get-CimAssociatedInstance -InputObject $disk -Association Win32_DiskDriveToDiskPartition | ForEach-Object { Get-CimAssociatedInstance -InputObject $_ -Association Win32_LogicalDiskToPartition | Where-Object { $_.DriveType -eq 2 -and $_.DeviceID -ne $env:SystemDrive } | ForEach-Object { $items+=@{root=($_.DeviceID+'/');description=$disk.Model;identity=$disk.PNPDeviceID} } } }; ConvertTo-Json -InputObject @($items) -Compress"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode or len(result.stdout) > 65536:
            raise ValueError("Enumeration failed")
        rows = json.loads(result.stdout)
        rows = rows if isinstance(rows, list) else [rows]
        return [
            {
                "root": r["root"],
                "model_profile": documented_model(r.get("description", "")),
                "source": "Nokia USB disk/CIM association",
                "identity": __import__("hashlib")
                .sha256(r.get("identity", "").encode())
                .hexdigest(),
            }
            for r in rows
            if isinstance(r, dict) and re.fullmatch("[D-Zd-z]:/", str(r.get("root", "")))
        ], None
    except (OSError, ValueError, subprocess.SubprocessError):
        return (
            [],
            "Windows Nokia disk enumeration is unavailable; enroll the memory card explicitly",
        )
