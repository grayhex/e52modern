import pytest

from symport.devices import profiles
from tests.helpers import REPO


def test_e52_profile_loads_and_marks_unknowns():
    p = profiles.load_profile(REPO / "profiles" / "nokia-e52.toml")
    assert p.id == "nokia-e52"
    assert p.value("platform.symbian_version") == "9.3"
    assert p.value("display.resolution") == [240, 320]
    unknown = set(p.summary()["unknown"])
    assert {"firmware.version", "firmware.rom_dlls", "device.product_code", "packaging.signing_policy"} <= unknown
    assert p.fact("firmware.version")["status"] == "unknown"
    assert p.fact("no.such.key")["status"] == "unknown"


def test_no_confirmed_fact_without_source():
    for f, v in profiles.load_profile(REPO / "profiles" / "nokia-e52.toml").facts():
        assert v["status"] == "unknown" or v["source"], f


@pytest.mark.parametrize("body, msg", [
    ('schema = 2\nid = "x"', "schema"),
    ('schema = 1', "id"),
    ('schema = 1\nid = "x"\n[a]\nb = { value = 1, status = "documented" }', "source"),
    ('schema = 1\nid = "x"\n[a]\nb = { value = 1, status = "unknown", source = "s" }', "unknown fact must not carry"),
    ('schema = 1\nid = "x"\n[a]\nb = { value = 1, status = "guess", source = "s" }', "status must be"),
])
def test_invalid_profiles_rejected(tmp_path, body, msg):
    p = tmp_path / "bad.toml"
    p.write_text(body)
    with pytest.raises(profiles.ProfileError, match=msg):
        profiles.load_profile(p)


def test_additional_profiles_are_just_files(tmp_path):
    (tmp_path / "nokia-e71.toml").write_text('schema = 1\nid = "nokia-e71"\n[device]\nmodel = { value = "E71", status = "stated", source = "test" }\n')
    ids = [p.id for p in profiles.list_profiles([tmp_path, REPO / "profiles"])]
    assert ids == ["nokia-e71", "nokia-e52", "nokia-e72", "nokia-n95-8gb", "nokia-n95", "nokia-n97-mini"]
    with pytest.raises(profiles.ProfileError, match="unknown device profile"):
        profiles.get_profile("nokia-n8", [tmp_path])


def test_e72_geometry_and_automatic_presentation():
    from symport.phone.models import presentation
    p = profiles.load_profile(REPO / 'profiles/nokia-e72.toml')
    assert p.value('display.resolution') == [320, 240]
    assert p.value('display.orientation') == 'landscape'
    e72 = presentation('Nokia E72 (RM-530)')
    assert e72['name'] == 'Nokia E72' and e72['screen']['width'] == 320
    assert presentation('E52')['screen']['height'] == 320
    assert presentation('a mounted folder') is None


def test_e72_artwork_keeps_handset_proportions():
    from PIL import Image
    with Image.open(REPO/'symport/web_assets/phones/nokia-e72.png') as image:
        left,top,right,bottom = image.getbbox()
        assert 1.85 < (bottom-top)/(right-left) < 2.10
