"""Verified Essentials (#40): per-model profiles from existing catalog cards, honest eligibility."""
import pytest

from symport.catalog.service import AppCatalog

MODELS = ("nokia-e52", "nokia-e72", "nokia-n95", "nokia-n95-8gb")


class NoDevices:
    pass


@pytest.fixture
def catalog(tmp_path):
    return AppCatalog(tmp_path, NoDevices())


def evaluate(catalog, profile, model):
    return catalog.execute({"action": "essentials", "profile": profile, "model": model})


def test_profiles_match_the_requested_set_and_reuse_catalog_cards(catalog):
    listing = catalog.execute({"action": "essentials"})
    assert [p["id"] for p in listing["profiles"]] == ["communication", "internet", "offline", "media", "tools", "n95-classic"]
    assert [p["title"]["ru"] for p in listing["profiles"]] == ["Связь", "Интернет", "Офлайн", "Медиа", "Файлы и инструменты", "N95 Classic / FP1"]
    assert "TLS" in listing["guide"]["en"][0] and any("offline" in line.lower() or "Offline" in line for line in listing["guide"]["en"])
    for p in listing["profiles"]:
        assert all(a in catalog.catalog.entries for a in p["apps"]), p["id"]


@pytest.mark.parametrize("model", ("nokia-e52", "nokia-e72"))
def test_fp2_profile_has_verifiable_static_items(catalog, model):
    result = evaluate(catalog, "tools", model)
    assert result["applicable"] and {"xplore", "ip-calculator", "passgen"} <= set(result["eligible_ids"])
    assert result["order"] and result["bytes"] > 0
    assert "Copying is not installation" in result["statement"]


@pytest.mark.parametrize("model", ("nokia-n95", "nokia-n95-8gb"))
def test_fp1_n95_classic_profile_has_verifiable_static_items(catalog, model):
    result = evaluate(catalog, "n95-classic", model)
    assert result["applicable"] and {"xplore", "gps-tracker", "s2putty"} <= set(result["eligible_ids"])
    for item in result["items"]:
        assert item["evidence"]["hardware"] == "not-tested" and item["evidence"]["installation"] == "not-tested"
        if item["eligible"]:
            assert item["evidence"]["pinned_sha256"]


def test_the_n95_profile_is_refused_for_other_models(catalog):
    result = evaluate(catalog, "n95-classic", "nokia-e52")
    assert result["applicable"] is False and result["eligible_ids"] == [] and "does not target" in result["reason"]
    with pytest.raises(ValueError, match="supported phone model"):
        evaluate(catalog, "offline", "nokia-n95-family")
    with pytest.raises(ValueError, match="supported phone model"):
        evaluate(catalog, "offline", "nokia-n97-mini-x")
    with pytest.raises(ValueError, match="Unknown essentials profile"):
        evaluate(catalog, "wipe", "nokia-e52")


def test_manual_only_unavailable_and_unsupported_cards_are_never_eligible(catalog):
    for model in MODELS:
        internet = {i["id"]: i for i in evaluate(catalog, "internet", model)["items"]}
        assert internet["opera-mini"]["eligible"] is False and any("manual-only" in r for r in internet["opera-mini"]["reasons"])
        tools = {i["id"]: i for i in evaluate(catalog, "tools", model)["items"]}
        assert tools["fshell"]["eligible"] is False and tools["pys60"]["eligible"] is False
    for model in MODELS:
        offline = evaluate(catalog, "offline", model)
        assert all(i["eligible"] is False for i in offline["items"] if not i["evidence"]["pinned_sha256"])


def test_eligible_items_are_pinned_and_listed_in_install_order(catalog):
    result = evaluate(catalog, "communication", "nokia-e52")
    assert set(result["order"]) >= set(result["eligible_ids"]) and len(result["order"]) == len(set(result["order"]))
    for item in result["items"]:
        if item["eligible"]:
            assert item["licence"] and item["author"] and item["size"] > 0


def test_a_profile_saves_as_an_ordinary_collection_for_the_existing_recovery_flow(catalog):
    saved = catalog.execute({"action": "essentials-collection", "profile": "offline", "model": "nokia-n95"})
    assert saved["profile"] == "nokia-n95" and saved["name"].startswith("Offline")
    assert {a["id"] for a in saved["apps"]} == set(evaluate(catalog, "offline", "nokia-n95")["eligible_ids"])
    assert all(a["artifacts"] for a in saved["apps"])
    with pytest.raises(ValueError, match="Nothing eligible"):
        catalog.execute({"action": "essentials-collection", "profile": "n95-classic", "model": "nokia-e52"})
