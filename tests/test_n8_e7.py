"""N8/E7 targets: real host files and explicit driver doubles, never hardware attestations."""

from __future__ import annotations

import base64
import copy
import json
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from symport.catalog.compatibility import assessment
from symport.catalog.model import Catalog
from symport.deps import analyze_package
from symport.devices.profiles import load_profile
from symport.firmware import FirmwareExplorer
from symport.firmware.preparation import manifest
from symport.phone import DeviceManager
from symport.phone.connections import load_profiles
from symport.phone.files import MountedVolumes
from symport.phone.gammu_adapter import GammuAdapter
from symport.phone.models import documented_model, presentation
from symport.phone.obex import ObexAdapter
from symport.phone.registry import identify, theme_profiles
from symport.theme.studio import ThemeStudio
from tests.helpers import REPO, make_e32
from tests.test_deps import QT, sis
from tests.test_transports import PROFILE

MODELS = [("N8", "RM-596", "nokia-n8"), ("E7", "RM-626", "nokia-e7")]


@pytest.mark.parametrize("name,rm,key", MODELS)
def test_model_rm_platform_and_source_profile_are_separate_from_current_firmware(name, rm, key):
    for alias in (name, name + "-00", "Nokia " + name.lower() + "-00 (" + rm + ")"):
        profile = presentation(alias)
        assert profile["id"] == key and profile["symbian"] is None
        assert profile["screen"]["width"] == 360 and profile["screen"]["height"] == 640
        assert (
            profile["hardware"] == "not-tested"
            and profile["theme_studio"]["status"] == "unsupported"
        )
    assert identify("", rm=rm)["id"] == key
    assert documented_model(name)["edition"] == "symbian3"
    assert identify("", product_code="unknown-code") is None
    p = load_profile(REPO / "profiles" / (key + ".toml"))
    for field in (
        "platform.symbian_version",
        "firmware.version",
        "device.product_code",
        "connection.write_permissions",
        "storage.mounted_volume",
    ):
        assert p.fact(field)["status"] == "unknown"
    assert p.value("device.rm") == rm and all(f["source"] for _, f in p.facts())


@pytest.mark.parametrize(
    "name,rm",
    [
        ("E7-01", None),
        ("XE7", None),
        ("N8-01", None),
        ("N8", "RM-626"),
        ("E7", "RM-596"),
        ("E7", "RM-530"),
        ("N8", "RM-999"),
        ("N95", "RM-626"),
        ("Nokia N97", "RM-596"),
        ("Nokia E71", "RM-626"),
    ],
)
def test_suffix_rm_and_other_models_do_not_falsely_resolve(name, rm):
    assert identify(name, rm=rm) is None
    assert presentation(name, rm=rm) is None


def test_e7_is_distinct_from_e72_and_model_does_not_guess_product_code():
    assert presentation("E72")["id"] == "nokia-e72"
    assert identify("E7", product_code="e72-code")["id"] == "nokia-e7"


@pytest.mark.parametrize("name,rm,key", MODELS)
def test_static_platform_checks_do_not_guess_belle_or_installed_qt(name, rm, key):
    target = {"model": name, "rm": rm}
    for old_uid in (0x101F7961, 0x102032BE, 0x102752AE, 0x1028315F):
        assert (
            analyze_package(sis(0xE0001111, "old-only", platforms=(old_uid,)), target=target)[
                "platform_verdict"
            ]
            == "unsupported"
        )
    raw = sis(0xE0001111, "base", platforms=(0x20022E6D,))
    assert analyze_package(raw, target=target)["platform_verdict"] == "supported-static"
    assert analyze_package(raw, target=dict(target, os="9.4"))["verdict"] == "blocked"
    belle = sis(0xE0001111, "Belle", platforms=(0x2003A678,))
    assert analyze_package(belle, target=target)["platform_verdict"] == "unknown"
    assert (
        analyze_package(belle, target=dict(target, os="Anna"))["platform_verdict"] == "unsupported"
    )
    for os in ("Belle", "Belle Refresh", "Symbian Belle"):
        report = analyze_package(belle, target=dict(target, os=os))
        assert (
            report["platform_verdict"] == "supported-static"
            and report["levels"]["physical_device"] == "not-tested"
        )
    qt = sis(
        0xE0001111,
        "Qt app",
        platforms=(0x20022E6D,),
        deps=[(QT, "Qt", (4, 7, 3))],
        exe=make_e32(imports={"qtcore.dll": [1], "euser.dll": [1]}),
    )
    report = analyze_package(qt, target=target)
    assert (
        report["verdict"] == "unresolved"
        and report["runtimes"][0]["status"] == "required-unverified"
    )
    assert "system-dll-unverified" in report["issues"]
    arm6 = analyze_package(
        sis(0xE0001111, "ARM6", platforms=(0x20022E6D,), exe=make_e32(cpu=0x2002)), target=target
    )
    assert "binary-abi-unknown" in arm6["issues"] and "binary-abi-unsupported" not in arm6["issues"]


@pytest.mark.parametrize("name,rm,key", MODELS)
def test_same_file_transport_transfers_valid_sis_and_preserves_safety_and_backup(
    tmp_path, name, rm, key
):
    volume = tmp_path / "mass-memory"
    volume.mkdir()
    manager = DeviceManager(tmp_path, MountedVolumes({"usb": str(volume)}))
    row = manager.execute({"action": "discover"})["devices"][0]
    assert row["model_profile"] is None and row["model"] is None
    assert row["capability_matrix"]["contacts.read"]["status"] == "unsupported"
    assert row["capability_matrix"]["sms.send"]["attempt"] == "blocked"
    raw = sis(0xE0001111, "Benign host fixture", platforms=(0x20022E6D,))
    request = {
        "action": "transfer",
        "device": "usb",
        "path": "test.sis",
        "content": base64.b64encode(raw).decode(),
    }
    with pytest.raises(ValueError, match="confirmation"):
        manager.execute(request)
    result = manager.execute(dict(request, confirm=True))
    assert result["status"] == "transferred-not-installed"
    download = manager.execute({"action": "download", "device": "usb", "path": "test.sis"})
    assert base64.b64decode(download["content"]) == raw
    with pytest.raises((ValueError, OSError)):
        manager.execute(dict(request, confirm=True))
    for path in ("../host.txt", "C:/private/secret", "sys/bin/app.exe"):
        with pytest.raises(ValueError):
            manager.execute(dict(request, action="upload", path=path, confirm=True))
    backup = manager.execute({"action": "backup", "device": "usb", "path": ""})
    assert backup["content"] and volume.joinpath("test.sis").read_bytes() == raw
    with pytest.raises(ValueError):
        manager.execute({"action": "personal-read", "device": "usb", "domain": "contacts"})


@pytest.mark.parametrize("kind", ["gammu-usb", "gammu-bluetooth", "gammu-s60", "gammu-obex"])
@pytest.mark.parametrize("name,rm,key", MODELS)
def test_gammu_can_probe_existing_driver_scopes_without_promoting_unread_stores(
    tmp_path, monkeypatch, kind, name, rm, key
):
    monkeypatch.setattr("symport.phone.gammu_adapter.gammu_native.available", lambda: True)
    config = tmp_path / "gammurc"
    config.write_text("[gammu]\ndevice=COM7\nconnection=at\n")
    adapter = GammuAdapter(tmp_path, "usb", str(config), kind=kind)
    adapter.personal.execute = lambda *args: {
        "model": name + "-00",
        "manufacturer": "Nokia",
        "rm": rm,
        "firmware": None,
        "capability_status": {
            "contacts": {"status": "available"},
            "sms": {"status": "unavailable", "reason": "ERR_NOTSUPPORTED"},
        },
    }
    row = adapter.device()
    assert row["connected"] and row["platform_info"]["edition"] == "symbian3"
    assert row["capability_matrix"]["contacts.read"]["status"] == "available"
    assert row["capability_matrix"]["sms.read"]["status"] == "unsupported"
    assert row["capability_matrix"]["calendar.read"]["status"] == "not-tested"
    assert row["capability_matrix"]["sms.send"]["attempt"] == "blocked"
    profile_file = tmp_path / "connections.json"
    profile_file.write_text(
        json.dumps(
            {
                "schema": 1,
                "connections": [
                    {
                        "id": "usb",
                        "kind": kind,
                        "manufacturer": "Nokia",
                        "platform": "S60",
                        "edition": "symbian3",
                        "config": str(config),
                    }
                ],
            }
        )
    )
    assert load_profiles(str(profile_file))[0]["edition"] == "symbian3"


@pytest.mark.parametrize("kind", ["obexftp", "obex-opp"])
def test_obex_is_enrolled_service_not_phone_or_pim_identity(kind):
    adapter = ObexAdapter(
        dict(PROFILE, edition="symbian3", kind=kind), lambda *a, **kw: b"<folder-listing/>"
    )
    row = adapter.device()
    assert (
        row["model"] is None
        and row["capability_matrix"]["contacts.read"]["status"] == "unsupported"
    )


@pytest.mark.parametrize("name,rm,key", MODELS)
def test_observed_os_needs_its_own_source_and_unknown_counters_stay_unknown(
    tmp_path, name, rm, key
):
    class Driver:
        def devices(self):
            return [
                dict(
                    id="usb",
                    model=name,
                    rm=rm,
                    transport="gammu",
                    connected=True,
                    capabilities=[],
                    os_release="Belle",
                    **extra,
                )
            ]

    extra = {}
    service = DeviceManager(tmp_path, Driver())
    row = service.execute({"action": "discover"})["devices"][0]
    assert row["model_profile"]["symbian"] is None
    extra["os_source"] = "synthetic native identity reply"
    row = service.execute({"action": "discover"})["devices"][0]
    assert (
        row["model_profile"]["symbian"] == "Belle"
        and row["model_profile"]["release_evidence"]["status"] == "observed"
    )
    assert not row.get("battery") and not row.get("firmware")


@pytest.mark.parametrize("name,rm,key", MODELS)
def test_themes_remain_blocked_even_with_own_artwork(tmp_path, name, rm, key):
    studio = ThemeStudio(tmp_path)
    assert key not in theme_profiles()
    for action in ("create", "import"):
        with pytest.raises(ValueError, match="Belle"):
            studio.execute(
                {"action": action, "profile": key, "name": "No theme", "content": "eA=="}
            )
    assert not list(studio.root.glob("*/project.json"))


@pytest.mark.parametrize("name,rm,key", MODELS)
def test_artwork_masters_are_self_contained_transparent_and_proportionate(name, rm, key):
    profile = presentation(name)
    root = ET.parse(REPO / f"symport/web_assets/phones/{key}.svg").getroot()
    assert all(
        n.get("href", "").startswith("data:image/png;base64,") for n in root.iter() if n.get("href")
    )
    geometry = profile["artwork"]
    assert geometry["screen"]["width"] / geometry["screen"]["height"] == 360 / 640
    for ext in ("png", "webp"):
        with Image.open(REPO / f"symport/web_assets/phones/{key}.{ext}") as image:
            assert image.mode == "RGBA" and image.size == (geometry["width"], geometry["height"])
            assert image.getpixel((0, 0))[3] == 0
            x, y, right, bottom = image.getbbox()
            assert 0.46 < (right - x) / (bottom - y) < 0.56


def test_catalog_does_not_reuse_s60v3_evidence_for_symbian3():
    entry = copy.deepcopy(Catalog(REPO / "catalog").entries["xplore"])
    entry.update(compatibility="verified-on-e52", e52_evidence=["https://example.com/test"])
    for key in ("nokia-n8", "nokia-e7"):
        assert assessment(entry, key)["status"] != "verified"
    entry["minimum_symbian"] = "Belle"
    entry["platforms"] = ["Symbian Belle"]
    assert assessment(entry, "nokia-e52")["status"] == "unsupported"
    assert assessment(entry, "nokia-n8")["status"] == "not-tested"


def vpl(rm="RM-626", keyboard="Russian"):
    return base64.b64encode(
        f"<VariantPackingList><VariantIdentification><ProductType>{rm}</ProductType><SwVersion>111.040.fixture</SwVersion><ProductCode>TEST-ONLY</ProductCode><Language>Russian</Language><Keyboard>{keyboard}</Keyboard></VariantIdentification></VariantPackingList>".encode()
    ).decode()


def test_cfw_preparation_uses_actual_manifest_and_never_offers_flashing(tmp_path):
    service = FirmwareExplorer(tmp_path)
    report = service.execute(
        {"action": "cfw-plan", "profile": "nokia-e7", "source": "reborn-n8-e7", "manifest": vpl()}
    )
    assert report["package"]["rm"] == "RM-626" and report["package"]["keyboard"] == "Russian"
    assert report["manifest"]["sha256"] and report["physical_device"] == "not-tested"
    assert report["flashing"] == "unsupported" and report["status"] == "research-only"
    bad = service.execute(
        {"action": "cfw-plan", "profile": "nokia-n8", "source": "reborn-n8-e7", "manifest": vpl()}
    )
    assert bad["status"] == "blocked"
    missing = service.execute(
        {
            "action": "cfw-plan",
            "profile": "nokia-e7",
            "source": "delight-belle",
            "declared": {"rm": "RM-626"},
        }
    )
    assert any(c["code"] == "keyboard" and c["status"] == "blocked" for c in missing["checks"])
    assert not list(tmp_path.iterdir())  # Preparation causes no write, download or phone operation.


def test_cfw_manual_fields_do_not_become_vpl_or_device_evidence(tmp_path):
    service = FirmwareExplorer(tmp_path)
    minimal = base64.b64encode(
        b"<VariantPackingList><ProductType>RM-596</ProductType></VariantPackingList>"
    ).decode()
    report = service.execute(
        {
            "action": "cfw-plan",
            "profile": "nokia-n8",
            "source": "reborn-n8-e7",
            "manifest": minimal,
            "declared": {"version": "user-only"},
        }
    )
    assert report["field_evidence"]["rm"]["basis"] == "vpl-metadata"
    assert report["field_evidence"]["version"]["basis"] == "user-declared"
    assert report["field_evidence"]["language"]["basis"] == "unknown"
    for bad in ([], {}, None):
        with pytest.raises(ValueError):
            service.execute({"action": "cfw-plan", "profile": bad})


@pytest.mark.parametrize(
    "raw",
    [
        b"<html>not a VPL</html>",
        b'<!DOCTYPE x [<!ENTITY a "x">]><VariantPackingList/>',
        "<!DOCTYPE x><VariantPackingList/>".encode("utf-16"),
        b"<VariantPackingList><ProductType>RM-596</ProductType><Other>RM-626</Other></VariantPackingList>",
    ],
)
def test_manifest_rejects_wrong_format_entities_and_conflicting_targets(raw):
    with pytest.raises(ValueError):
        manifest(base64.b64encode(raw).decode())
