"""Read-only CFW preparation. Parses a small user VPL; never writes to a phone or flashes."""

from __future__ import annotations

import base64
import hashlib
import re
from xml.etree import ElementTree as ET

from symport.phone.registry import identify, registry

from .cfw import load_sources


def manifest(content):
    if not content:
        return None
    if not isinstance(content, str) or len(content) > 700_000:
        raise ValueError("VPL limit: 512 KiB")
    try:
        raw = base64.b64decode(content, validate=True)
        # Reject DTD/entity declarations also in UTF-16 documents, before any XML parsing.
        check = raw.replace(b"\x00", b"").upper()
        if len(raw) > 512 * 1024 or b"<!DOCTYPE" in check or b"<!ENTITY" in check:
            raise ValueError("Unsafe or oversized VPL")
        root = ET.fromstring(raw)
    except (ValueError, ET.ParseError) as exc:
        raise ValueError("Invalid or unsafe VPL XML") from exc
    nodes = list(root.iter())
    if len(nodes) > 5000 or root.tag.rsplit("}", 1)[-1] != "VariantPackingList":
        raise ValueError("Expected Nokia VariantPackingList")
    fields = {}
    for key, tags in {
        "version": ("swversion", "softwareversion"),
        "product_code": ("productcode",),
        "language": ("language", "languages"),
        "keyboard": ("keyboard", "keyboardlayout"),
    }.items():
        values = {
            n.text.strip()[:160]
            for n in nodes
            if n.tag.rsplit("}", 1)[-1].casefold() in tags and n.text and n.text.strip()
        }
        if len(values) > 1:
            raise ValueError("Conflicting VPL field: " + key)
        fields[key] = next(iter(values), None)
    rms = sorted(set(re.findall(r"\bRM-\d+\b", " ".join(n.text or "" for n in nodes).upper())))
    if len(rms) > 1:
        raise ValueError("Conflicting RM codes in VPL")
    return {
        **fields,
        "rm": rms[0] if rms else None,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "basis": "user-supplied VPL metadata; unsigned and not authenticated by SymPort",
    }


def plan(store, devices, data):
    if not isinstance(data.get("profile"), str):
        raise ValueError("Choose Nokia N8 or E7")
    profile = registry().get(data.get("profile"))
    if not profile or profile.get("platform_family") != "symbian3":
        raise ValueError("Choose Nokia N8 or E7")
    source = next((s for s in load_sources()["sources"] if s["id"] == data.get("source")), None)
    if not source or source.get("symport", {}).get(profile["id"]) != "research-only":
        raise ValueError("CFW source does not target this model")
    declared = data.get("declared") or {}
    if not isinstance(declared, dict):
        raise ValueError("Expected package metadata")
    if any(value is not None and not isinstance(value, str) for value in declared.values()):
        raise ValueError("Package metadata fields must be text")
    declared = {
        k: str(declared.get(k) or "").strip()[:160]
        for k in ("rm", "version", "product_code", "language", "keyboard")
    }
    vpl = manifest(data.get("manifest"))
    package = {k: (vpl or {}).get(k) or declared[k] or None for k in declared}
    field_evidence = {
        key: {
            "value": value,
            "basis": "vpl-metadata"
            if (vpl or {}).get(key)
            else "user-declared"
            if declared[key]
            else "unknown",
        }
        for key, value in package.items()
    }
    checks = []

    def add(code, status, en, ru):
        checks.append({"code": code, "status": status, "text": {"en": en, "ru": ru}})

    for key in declared:
        if vpl and vpl.get(key) and declared[key] and vpl[key] != declared[key]:
            add(
                "metadata-conflict-" + key,
                "blocked",
                f"VPL and manual {key} disagree.",
                f"VPL и ручное поле {key} не совпадают.",
            )
    expected_rm = profile["rms"][0]
    add(
        "rm",
        "matched-static"
        if package["rm"] == expected_rm
        else "blocked"
        if package["rm"]
        else "unknown",
        f"Package RM: {package['rm'] or 'unknown'}; target: {expected_rm}.",
        f"RM пакета: {package['rm'] or 'неизвестен'}; цель: {expected_rm}.",
    )
    for key in ("version", "product_code", "language"):
        add(
            key,
            "declared" if package[key] else "unknown",
            f"Package {key}: {package[key] or 'unknown'}.",
            f"{key} пакета: {package[key] or 'неизвестно'}.",
        )
    if profile["input"] == "touch-qwerty-slider":
        add(
            "keyboard",
            "declared" if package["keyboard"] else "blocked",
            "Confirm the package keyboard variant against the physical E7 keyboard; UI language is insufficient.",
            "Сверьте раскладку пакета с физической клавиатурой E7; языка интерфейса недостаточно.",
        )
    rows = devices.execute({"action": "discover"})["devices"] if devices else []
    row = next((r for r in rows if r["id"] == data.get("device")), None)
    verified_identity = bool(
        row
        and row.get("connected")
        and row.get("capability_matrix", {}).get("identity.read", {}).get("status") == "available"
    )
    identity = (
        identify(str((row or {}).get("model") or ""), rm=(row or {}).get("rm"))
        if verified_identity
        else None
    )
    add(
        "device",
        "matched-static"
        if identity and identity["id"] == profile["id"]
        else "blocked"
        if identity
        else "unknown",
        "A mounted filesystem does not identify the phone; observed identity must match separately.",
        "Файловый том не идентифицирует телефон; ответ устройства должен совпасть отдельно.",
    )
    observed_version = (row or {}).get("firmware") if verified_identity else None
    add(
        "firmware-comparison",
        "review" if observed_version and package["version"] else "unknown",
        f"Observed firmware: {observed_version or 'unknown'}; package: {package['version'] or 'unknown'}. Confirm the exact source build and recovery procedure; no upgrade is approved here.",
        f"Прошивка устройства: {observed_version or 'не сообщена'}; пакет: {package['version'] or 'неизвестен'}. Сверьте точную сборку и восстановление; обновление здесь не разрешается.",
    )
    observed_code = (row or {}).get("product_code") if verified_identity else None
    if observed_code and package["product_code"] and observed_code != package["product_code"]:
        add(
            "product-code-conflict",
            "blocked",
            "Device and package product codes differ; review the variant.",
            "Коды продукта устройства и пакета различаются; проверьте модификацию.",
        )
    image = None
    if data.get("image"):
        meta = store._meta(data["image"])
        index = store.index(data["image"])
        image = {
            "id": meta["id"],
            "sha256": index["source"]["sha256"],
            "kind": meta["kind"],
            "files": meta["files"],
        }
    add(
        "image",
        "indexed" if image else "unknown",
        "Index the supplied unpacked ZIP/core ROM in Firmware Explorer; FPSX/ROFS payloads are not decoded.",
        "Проиндексируйте свой распакованный ZIP/core ROM в Firmware Explorer; содержимое FPSX/ROFS не декодируется.",
    )
    add(
        "backup",
        "user-confirmed" if data.get("backup_confirmed") is True else "unknown",
        "File backup covers only selected files. Keep PIM/Nokia Suite exports and recovery information separately.",
        "Файловая копия покрывает выбранные файлы. Сохраните PIM/экспорт Nokia Suite и сведения восстановления отдельно.",
    )
    return {
        "schema": "symport.cfw-preparation/1",
        "profile": profile["id"],
        "source": source["id"],
        "package": package,
        "field_evidence": field_evidence,
        "metadata_basis": vpl["basis"] if vpl else "user-declared; not verified",
        "manifest": vpl,
        "image": image,
        "checks": checks,
        "status": "blocked" if any(c["status"] == "blocked" for c in checks) else "research-only",
        "device_firmware": (row or {}).get("firmware"),
        "physical_device": "not-tested",
        "flashing": "unsupported",
        "steps": [
            "Compare exact RM, product code, firmware and E7 keyboard with the author release.",
            "Keep private backups and a separately verified recovery procedure.",
            "Review the supplied image inventory/advisories in CFW Research.",
        ],
        "statement": "Preparation and static metadata only. No flashing, installation, ROM writes or guarantee of recovery.",
    }
