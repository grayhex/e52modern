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
    assert ids == ["nokia-e71", "nokia-e52"]
    with pytest.raises(profiles.ProfileError, match="unknown device profile"):
        profiles.get_profile("nokia-n8", [tmp_path])
