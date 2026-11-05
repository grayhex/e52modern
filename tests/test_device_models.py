"""Model registry: adding a Nokia S60 phone is a data change; unknown geometry is never invented."""
import json

import pytest

from symport.phone import models


def test_registry_ships_e52_and_e72_with_artwork_and_geometry():
    by_model = {m["model"]: m for m in models.catalog()}
    assert by_model["E52"]["screen"] == {"width": 240, "height": 320, "orientation": "portrait"}
    assert by_model["E72"]["screen"] == {"width": 320, "height": 240, "orientation": "landscape"}
    assert by_model["E72"]["symbian"] == "9.3" and by_model["E72"]["s60"] == "3rd FP2"
    for entry in by_model.values():
        assert (models.REGISTRY_FILE.parents[1] / "web_assets" / entry["image"].lstrip("/")).is_file()


def test_presentation_for_registered_models_is_unchanged():
    e52 = models.presentation("Nokia E52 (RM-469)")
    assert e52["id"] == "nokia-e52" and e52["input"] == "numeric-keypad" and e52["image"].endswith(".png")
    assert models.presentation("Nokia E72")["screen"]["orientation"] == "landscape"


def test_documented_model_without_registry_entry_gets_identity_but_no_invented_artwork():
    e71 = models.presentation("Nokia E71 (RM-346)")
    assert e71["id"] == "nokia-e71" and e71["name"] == "Nokia E71"
    assert e71["image"] is None and e71["screen"] is None and e71["input"] is None
    assert e71["s60"] == "3rd FP1" and e71["symbian"] == "9.2"
    n97 = models.presentation("Nokia N97")
    assert n97["s60"] == "5th" and n97["symbian"] == "9.4"


def test_unknown_or_foreign_models_have_no_profile():
    assert models.presentation("Nokia 6300") is None
    assert models.presentation("Sony Ericsson K800") is None
    assert models.presentation("") is None


def write(tmp_path, *entries):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"schema": 1, "models": list(entries)}))
    return path


GOOD = {"id": "nokia-e71", "model": "E71", "name": "Nokia E71", "family": "Eseries",
        "image": "/phones/nokia-e71.png", "screen": {"width": 320, "height": 240, "orientation": "landscape"},
        "input": "qwerty", "toolchain_profile": None, "source": "test"}


def test_adding_a_phone_is_only_a_registry_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "REGISTRY_FILE", write(tmp_path, GOOD))
    profile = models.presentation("Nokia E71")
    assert profile["image"] == "/phones/nokia-e71.png" and profile["screen"]["width"] == 320
    assert profile["symbian"] == "9.2"
    assert [m["id"] for m in models.catalog()] == ["nokia-e71"]


@pytest.mark.parametrize("change", [
    {"id": "e71"}, {"id": "nokia-e71", "model": "6300"}, {"image": "/phones/../x.png"},
    {"image": "https://evil.example/x.png"}, {"screen": {"width": 10, "height": 240, "orientation": "landscape"}},
    {"screen": {"width": 320, "height": 240, "orientation": "diagonal"}}, {"unknown_field": 1},
])
def test_invalid_registry_entries_fail_loudly(tmp_path, change):
    with pytest.raises(ValueError):
        models.load_registry(write(tmp_path, {**GOOD, **change}))


def test_duplicate_ids_and_unknown_schema_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        models.load_registry(write(tmp_path, GOOD, GOOD))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": 2, "models": []}))
    with pytest.raises(ValueError):
        models.load_registry(bad)


def test_discover_exposes_the_registry(tmp_path):
    from symport.phone import DeviceManager
    from symport.phone.files import MountedVolumes

    class T:
        def devices(self):
            return MountedVolumes({}).devices()

        def execute(self, data):
            return {}

    result = DeviceManager(tmp_path, T()).execute({"action": "discover"})
    assert {m["model"] for m in result["models"]} >= {"E52", "E72"}
