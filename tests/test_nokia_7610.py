"""Nokia 7610 (original, Symbian OS 7.0s / S60 2nd Edition): a documented model, never a measured one.

Identity, platform and artwork come from the registry; capabilities come only from the transport.
Nothing here is a hardware attestation.
"""

from __future__ import annotations

import base64
import json

import pytest
from PIL import Image

from symport.catalog.compatibility import evidence
from symport.catalog.model import Catalog
from symport.deps import analyze_package
from symport.devices.profiles import load_profile
from symport.phone import DeviceManager
from symport.phone.connections import load_profiles
from symport.phone.files import MountedVolumes
from symport.phone.gammu_adapter import GammuAdapter
from symport.phone.models import documented_model, load_registry, presentation
from symport.phone.obex import ObexAdapter
from symport.phone.registry import identify, registry, selectable_profiles, theme_profiles
from symport.theme.studio import ThemeStudio
from tests.capfake import row
from tests.helpers import REPO
from tests.test_deps import sis
from tests.test_transports import PROFILE

PHONES = REPO / "symport" / "web_assets" / "phones"
OLDER_MODELS = ["nokia-e52", "nokia-e72", "nokia-n95", "nokia-n95-8gb", "nokia-n97-mini"]


# ---- identity ------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["7610", "Nokia 7610", "nokia 7610", "Nokia  7610"])
def test_model_name_resolves_to_a_documented_profile_not_a_measurement(name):
    profile = presentation(name)
    assert profile["id"] == "nokia-7610" and profile["name"] == "Nokia 7610"
    assert profile["s60"] == "2nd" and profile["symbian"] == "7.0s"
    assert profile["platform_family"] == "s60v2"
    assert profile["screen"] == {"width": 176, "height": 208, "orientation": "portrait"}
    assert profile["source"] == "documented-model-profile"
    assert profile["identity_basis"] == "reported-model" and profile["variant_known"] is True
    assert profile["measured"] is False and profile["hardware"] == "not-tested"
    assert profile["fact_status"] == "documented"
    assert documented_model(name)["edition"] == "2nd"


@pytest.mark.parametrize(
    "name",
    [
        "Nokia 7610 Supernova",
        "7610 Supernova",
        "NOKIA 7610 SUPERNOVA (RM-???)",
        "Nokia 7610supernova",
        "Nokia 7610s",
        "7610-1",
        "76100",
        "Nokia 7600",
        "Nokia 6670",
        "Nokia 7650",
    ],
)
def test_it_is_never_confused_with_7610_supernova_or_neighbouring_models(name):
    assert identify(name) is None
    assert presentation(name) is None
    assert documented_model(name) is None


def test_a_series_40_name_does_not_inherit_the_symbian_profile_through_a_reported_rm():
    # A registered RM of another model plus the 7610 name is conflicting evidence, never a guessed 7610.
    assert presentation("Nokia 7610", rm="RM-626") is None  # RM-626 is the E7
    assert presentation("Nokia 7610", rm="RM-596") is None  # RM-596 is the N8
    assert presentation("Nokia 7610 Supernova", rm="RM-626") is None
    # An RM that no registry entry knows stays a plain observation; it does not turn into an identity.
    assert presentation("Nokia 7610", rm="RM-1")["id"] == "nokia-7610"
    assert identify("", rm="RM-1") is None


def test_registry_entry_is_a_strict_valid_selectable_target_without_theme_support():
    entry = registry()["nokia-7610"]
    assert entry["selectable"] is True and entry["toolchain_profile"] == "nokia-7610"
    assert entry["rms"] == [] and entry["platform_uids"] == []
    assert entry["not_aliases"] == ["SUPERNOVA"]
    assert entry["theme_studio"]["status"] == "unsupported"
    assert "nokia-7610" in selectable_profiles() and "nokia-7610" not in theme_profiles()
    assert [m["id"] for m in load_registry()].count("nokia-7610") == 1


def test_profile_facts_are_sourced_and_unmeasured_values_stay_unknown():
    p = load_profile(REPO / "profiles" / "nokia-7610.toml")
    assert p.value("platform.symbian_version") == "7.0s"
    assert p.value("display.resolution") == [176, 208]
    assert p.value("device.model") == "7610"
    for field in (
        "device.rm",
        "device.product_code",
        "firmware.version",
        "firmware.rom_dlls",
        "storage.mounted_volume",
        "storage.free_bytes",
        "connection.write_permissions",
        "connection.services",
        "packaging.platform_dependency",
        "packaging.signing_policy",
        "display.rotation_state",
    ):
        assert p.fact(field)["status"] == "unknown", field
    # EKA1 kernel and the legacy installer are inferences from the OS release, not documentation.
    assert p.fact("platform.kernel")["status"] == "inferred"
    assert p.fact("platform.installer_format")["status"] == "inferred"
    assert all(f["source"] for _, f in p.facts())


def test_the_original_model_is_not_the_supernova_in_the_profile_either():
    text = (REPO / "profiles" / "nokia-7610.toml").read_text(encoding="utf-8")
    assert "Supernova" in text and "NOT" in text


# ---- artwork -------------------------------------------------------------------------------------
def test_artwork_masters_and_exports_exist_with_transparency_and_handset_proportions():
    assert registry()["nokia-7610"]["image"] == "/phones/nokia-7610.png"
    svg = (PHONES / "nokia-7610.svg").read_text(encoding="utf-8")
    assert "<image" not in svg and "href=" not in svg  # vector only, no embedded or external raster
    for layer in ('id="body"', 'id="display"', 'id="keypad"', 'id="lcd"'):
        assert layer in svg
    for suffix in (".png", ".webp"):
        with Image.open(PHONES / ("nokia-7610" + suffix)) as image:
            assert image.mode == "RGBA" and image.getchannel("A").getextrema()[0] == 0
            left, top, right, bottom = image.getbbox()
            assert 1.9 < (bottom - top) / (right - left) < 2.2


# ---- platform rules: S60 2nd Edition is a different, older platform ----------------------------
TARGET = {"model": "7610"}


def test_package_analysis_never_says_satisfied_and_does_not_reuse_s60_3rd_5th_rules():
    # Nothing is shipped as a verified S60 2nd Edition platform ID; nothing is "accepted by target".
    for uid in (0x101F7961, 0x102032BE, 0x102752AE, 0x1028315F):
        report = analyze_package(sis(0xE0001111, "pkg", platforms=(uid,)), target=TARGET)
        assert report["platform_verdict"] == "unsupported"  # built for S60 3rd/5th, a known mismatch
        assert report["verdict"] == "blocked"
        assert "legacy-platform-not-assessed" in report["issues"]
    unknown = analyze_package(sis(0xE0001111, "pkg", platforms=(0x10000001,)), target=TARGET)
    assert unknown["platform_verdict"] == "unknown" and unknown["verdict"] == "unresolved"
    undeclared = analyze_package(sis(0xE0001111, "pkg", platforms=()), target=TARGET)
    assert undeclared["verdict"] == "unresolved"
    for report in (unknown, undeclared):
        assert report["levels"]["physical_device"] == "not-tested"
        assert any("S60 2nd Edition" in line for line in report["limitations"])
        assert all(p["relation"] != "accepted-by-target" for p in report["platforms"])


def test_the_same_packages_for_other_models_are_unchanged():
    raw = sis(0xE0001111, "pkg", platforms=(0x101F7961,))
    e52 = analyze_package(raw, target={"model": "E52"})
    assert e52["platform_verdict"] == "supported-static"
    assert "legacy-platform-not-assessed" not in e52["issues"]


def test_catalog_compatibility_for_the_7610_is_never_compatible_or_verified():
    entries = Catalog(REPO / "catalog").entries.values()
    assert entries
    for entry in entries:
        result = evidence(entry)["nokia-7610"]
        assert result["status"] in ("not-tested", "unsupported", "unavailable"), entry["id"]
        assert result["status"] != "verified" and result["installation"] == "not-tested"
        assert result["platform"] == "2nd" and result["symbian"] == "7.0s"


def test_older_models_keep_their_catalog_results():
    entries = Catalog(REPO / "catalog").entries.values()
    for entry in entries:
        got = evidence(entry)
        assert set(OLDER_MODELS) <= set(got)
        assert got["nokia-e52"]["status"] in ("verified", "not-tested", "unsupported", "unavailable")
    xplore = Catalog(REPO / "catalog").entries["xplore"]
    assert xplore["model_compatibility"]["nokia-e52"]["platform"] == "3rd FP2"
    assert xplore["platform_compatibility"]["s60-2nd"]["status"] in ("not-tested", "unsupported")


# ---- transports: the 7610 adds no capability of its own -----------------------------------------
def test_mounted_volume_is_files_only_and_never_a_phone_identity_or_pim_source(tmp_path):
    volume = tmp_path / "rs-mmc"
    volume.mkdir()
    manager = DeviceManager(tmp_path, MountedVolumes({"card": str(volume)}))
    found = manager.execute({"action": "discover"})["devices"][0]
    assert found["model_profile"] is None and found["model"] is None  # a host folder is not a 7610
    assert found["capability_matrix"]["contacts.read"]["status"] == "unsupported"
    assert found["capability_matrix"]["sms.send"]["attempt"] == "blocked"
    raw = sis(0xE0001111, "pkg", platforms=(0x101F7961,))
    request = {
        "action": "transfer",
        "device": "card",
        "path": "pkg.sis",
        "content": base64.b64encode(raw).decode(),
    }
    with pytest.raises(ValueError, match="confirmation"):
        manager.execute(request)
    assert manager.execute(dict(request, confirm=True))["status"] == "transferred-not-installed"
    for path in ("../host.txt", "sys/bin/app.exe", "private/10003a3f/x"):
        with pytest.raises(ValueError):
            manager.execute(dict(request, action="upload", path=path, confirm=True))


@pytest.mark.parametrize("kind", ["gammu-usb", "gammu-bluetooth", "gammu-obex"])
def test_gammu_identity_alone_enables_no_personal_data_store(tmp_path, monkeypatch, kind):
    monkeypatch.setattr("symport.phone.gammu_adapter.gammu_native.available", lambda: True)
    config = tmp_path / "gammurc"
    config.write_text("[gammu]\ndevice=COM7\nconnection=at\n")
    adapter = GammuAdapter(tmp_path, "usb", str(config), kind=kind)
    adapter.personal.execute = lambda *args: {
        "model": "7610",
        "manufacturer": "Nokia",
        "rm": None,
        "firmware": None,
        "capability_status": {},  # the driver read the identity but probed no store
    }
    device = adapter.device()
    assert device["connected"] and device["platform_info"]["edition"] == "2nd"
    matrix = device["capability_matrix"]
    for store in ("contacts.read", "calendar.read", "sms.read"):
        assert matrix[store]["status"] in ("not-tested", "unsupported"), store
    assert matrix["sms.send"]["attempt"] == "blocked"
    assert not device.get("battery") and not device.get("firmware")


def test_a_probed_store_is_enabled_alone_and_partial_support_stays_partial(tmp_path, monkeypatch):
    monkeypatch.setattr("symport.phone.gammu_adapter.gammu_native.available", lambda: True)
    config = tmp_path / "gammurc"
    config.write_text("[gammu]\ndevice=COM7\nconnection=at\n")
    adapter = GammuAdapter(tmp_path, "usb", str(config), kind="gammu-usb")
    adapter.personal.execute = lambda *args: {
        "model": "7610",
        "manufacturer": "Nokia",
        "capability_status": {
            "contacts": {"status": "available"},
            "sms": {"status": "unavailable", "reason": "ERR_NOTSUPPORTED"},
        },
    }
    matrix = adapter.device()["capability_matrix"]
    assert matrix["contacts.read"]["status"] == "available"
    assert matrix["sms.read"]["status"] == "unsupported"
    assert matrix["calendar.read"]["status"] == "not-tested"
    assert matrix["contacts.write"]["status"] != "available"  # a read probe never proves a write


def test_enrolled_connection_profiles_accept_the_2nd_edition_but_nothing_older_or_newer(tmp_path):
    def enroll(edition):
        file = tmp_path / "connections.json"
        file.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "connections": [
                        {
                            "id": "usb",
                            "kind": "gammu-usb",
                            "manufacturer": "Nokia",
                            "platform": "S60",
                            "edition": edition,
                            "config": str(tmp_path / "gammurc"),
                        }
                    ],
                }
            )
        )
        return load_profiles(str(file))

    (tmp_path / "gammurc").write_text("[gammu]\ndevice=COM7\nconnection=at\n")
    assert enroll("2nd")[0]["edition"] == "2nd"
    for bad in ("1st", "4th", "symbian9"):
        with pytest.raises(ValueError, match="2nd/3rd/5th"):
            enroll(bad)


def test_obex_ftp_lists_but_opp_offers_no_file_access_and_neither_identifies_a_phone():
    ftp = ObexAdapter(
        dict(PROFILE, edition="2nd", kind="obexftp"), lambda *a, **kw: b"<folder-listing/>"
    ).device()
    assert ftp["model"] is None and ftp["capability_matrix"]["files.list"]["status"] == "available"
    assert ftp["capability_matrix"]["files.download"]["status"] == "not-tested"  # listing != download
    assert ftp["capability_matrix"]["contacts.read"]["status"] == "unsupported"
    opp = ObexAdapter(
        dict(PROFILE, edition="2nd", kind="obex-opp"), lambda *a, **kw: b"<folder-listing/>"
    ).device()
    assert opp["model"] is None
    for op in ("files.list", "files.download", "files.upload", "media.read", "contacts.read"):
        assert opp["capability_matrix"][op]["status"] == "unsupported", op


def test_a_transport_row_gets_the_documented_profile_but_no_invented_telemetry(tmp_path):
    class Driver:
        def devices(self):
            return [
                row(
                    dict(id="usb", transport="gammu", connected=True, model="7610"),
                    available=["identity.read"],
                )
            ]

    found = DeviceManager(tmp_path, Driver()).execute({"action": "discover"})["devices"][0]
    assert found["model_profile"]["id"] == "nokia-7610"
    assert found["model_profile"]["symbian"] == "7.0s"
    assert not found.get("battery") and not found.get("signal") and not found.get("firmware")
    assert found["capability_matrix"]["contacts.read"]["status"] != "available"


# ---- out of scope: themes ----------------------------------------------------------------------
def test_theme_studio_refuses_the_7610(tmp_path):
    studio = ThemeStudio(tmp_path)
    assert "nokia-7610" not in studio.execute({"action": "list"})["profiles"]
    with pytest.raises(ValueError):
        studio.execute({"action": "create", "profile": "nokia-7610", "name": "No theme"})


# ---- no regressions ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name,key",
    [
        ("E52", "nokia-e52"),
        ("Nokia E72", "nokia-e72"),
        ("N95 8GB", "nokia-n95-8gb"),
        ("Nokia N97 mini", "nokia-n97-mini"),
        ("N8-00", "nokia-n8"),
        ("E7-00", "nokia-e7"),
    ],
)
def test_other_models_still_resolve_as_before(name, key):
    resolved = presentation(name)
    assert resolved and resolved["id"] == key
    assert resolved.get("platform_family") != "s60v2"
    assert identify("N95")["variant_known"] is False
    assert identify("N97") is None


# ---- Inspector -----------------------------------------------------------------------------------
def test_inspector_result_for_the_7610_stays_unknown_and_does_not_apply_s60_3rd_rules(tmp_path):
    from symport.inspector.service import Inspector
    from tests.helpers import make_e32

    packages = {
        "declared-3rd.sis": sis(0xE0001111, "pkg", platforms=(0x101F7961,)),
        "unknown-platform.sis": sis(
            0xE0001111, "pkg", platforms=(0x10000001,), exe=make_e32(imports={"euser.dll": [1]})
        ),
    }
    resolver = lambda data: (data["name"], packages[data["name"]], "app")  # noqa: E731
    devices = DeviceManager(tmp_path, MountedVolumes({}))
    inspector = Inspector(tmp_path, resolver, devices, lab=None)
    for name in packages:
        report = inspector.execute(
            {"action": "analyze", "name": name, "target": {"model": "7610"}, "at": "2030-01-01"}
        )
        assert report["compatibility"] == "unknown", report["compatibility"]
        assert report["physical_device"] == "not-tested" and report["emulator"] == "not-tested"
        assert any("S60 2nd Edition" in line for line in report["limitations"])
        if name == "unknown-platform.sis":
            # No 3rd/5th "wrong OS" rule is applied; only a package that itself declares S60 3rd/5th differs.
            assert "unsupported-os" not in report["issues"]
        assert report["dependency_analysis"]["verdict"] in ("blocked", "unresolved")
        assert all(b["compatibility"] != "compatible" for b in report["binaries"])
    # The very same package is judged by the real rules for a model whose platform is verified.
    e52 = inspector.execute(
        {"action": "analyze", "name": "declared-3rd.sis", "target": {"model": "E52", "os": "9.3"}, "at": "2030-01-01"}
    )
    assert "legacy-platform-not-assessed" not in e52["dependency_analysis"]["issues"]


def test_binaries_are_not_judged_against_s60_3rd_5th_abi_rules_on_the_7610():
    from tests.helpers import make_e32

    exe = make_e32(imports={"euser.dll": [1]}, cpu=0x2002)  # an ARMv6 image: a defect for E52, unknown for 7610
    raw = sis(0xE0001111, "pkg", platforms=(0x101F7961,), exe=exe)
    other = analyze_package(raw, target={"model": "E52"})
    assert "binary-abi-unsupported" in other["issues"]
    legacy = analyze_package(raw, target=TARGET)
    assert "binary-abi-unsupported" not in legacy["issues"]
    assert "binary-kernel-unsupported" not in legacy["issues"]
    assert "binary-abi-unknown" in legacy["issues"]
