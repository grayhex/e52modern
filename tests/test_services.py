"""Legacy Services Revival (#37): registry honesty, per-model statuses, server-side diagnostics, records."""
import pytest

from symport.phone import DeviceManager
from symport.revive import ReviveService
from symport.revive.services import default_probe, load
from tests.test_revive import Fake, phone

REGISTRY = load()
TARGETS = ("nokia-e52", "nokia-e72", "nokia-n95", "nokia-n95-8gb", "nokia-n97-mini")


def svc_with(tmp_path, *rows):
    return ReviveService(tmp_path, DeviceManager(tmp_path, Fake(*rows)))


def statuses(state, sid):
    return {m["target"]: m["services"][sid]["status"] for m in state["matrix"]}


def test_registry_cites_its_source_and_never_invents_original_urls():
    reborn = [s for s in REGISTRY["services"] if s["origin"]["kind"] == "reborncfw"]
    assert len(reborn) == 10
    for s in reborn:
        assert s["origin"]["repository"] == "https://github.com/symbuzzer/reborncfw" and "GPL-3.0" in s["origin"]["licence"]
        assert s["original_url"] is None and "does not state" in s["original_url_note"]
        assert s["substitute"]["trust"] == "third-party-unverified"
    assert REGISTRY["services"][0]["substitute"]["entry"] == "https://symbuzzer.github.io/reborncfw/conntest/"


def test_belle_endpoints_are_unsupported_on_every_s60_target(tmp_path):
    state = svc_with(tmp_path, phone()).execute({"action": "services-state", "device": "usb"})
    for sid in ("reborn-update-n8", "reborn-update-e7", "reborn-uaprof-n8", "reborn-uaprof-e7"):
        assert set(statuses(state, sid).values()) == {"unsupported"}, sid
    reason = state["matrix"][0]["services"]["reborn-uaprof-n8"]["reason"]["en"]
    assert "Belle" in reason and "not carried over" in reason


def test_nothing_is_ever_marked_available_without_evidence(tmp_path):
    state = svc_with(tmp_path, phone()).execute({"action": "services-state", "device": "usb"})
    seen = {c["status"] for m in state["matrix"] for c in m["services"].values()}
    assert "available" not in seen and seen <= {"unsupported", "manual-setup-required", "not-confirmed"}
    assert set(statuses(state, "reborn-homepage").values()) == {"manual-setup-required"}
    assert set(statuses(state, "agps-supl").values()) == {"not-confirmed"}
    assert {m["target"] for m in state["matrix"]} == set(TARGETS)
    assert state["bridge"]["status"] == "not-implemented" and "SSRF protection" in state["bridge"]["requirements"]


def test_empty_states_without_a_phone(tmp_path):
    state = svc_with(tmp_path).execute({"action": "services-state"})
    assert state["reason"] == "no-connection" and state["services"] and state["profile"] is None


def test_diagnostics_say_where_they_ran_and_detect_redirect_drift(tmp_path):
    svc = svc_with(tmp_path, phone())

    def probe(url, hosts):
        if "conntest" in url:
            return {"ok": True, "status": 200, "location": None, "meta_refresh": "https://avalibeyaz.com/s3/connecttest.php"}
        if "homepage" in url:
            return {"ok": True, "status": 200, "location": None, "meta_refresh": "https://evil.example/"}
        if "/store/" in url:
            return {"ok": False, "error": "offline"}
        return {"ok": True, "status": 200, "location": None, "meta_refresh": None}

    svc.services.probe = probe
    result = svc.execute({"action": "services-diagnose"})
    by = {r["id"]: r for r in result["results"]}
    assert result["ran_on"] == "server" and "says nothing about the phone" in result["statement"]
    assert by["reborn-conntest"]["status"] == "matches-registry"
    assert by["reborn-homepage"]["status"] == "drifted" and by["reborn-homepage"]["live_target"] == "https://evil.example/"
    assert by["reborn-store"]["status"] == "unreachable"
    assert by["reborn-tts"]["status"] == "no-redirect-found"
    assert by["reborn-uaprof-n8"]["status"] == "reachable"
    assert by["reborn-update-n8"]["status"] == "not-probed" and by["reborn-update-n8"]["reason"] == "registry-has-no-target"


def test_misspelled_host_is_not_probed(tmp_path):
    svc = svc_with(tmp_path, phone())
    calls = []
    svc.services.probe = lambda url, hosts: calls.append(url) or {"ok": True, "status": 200, "meta_refresh": None}
    by = {r["id"]: r for r in svc.execute({"action": "services-diagnose"})["results"]}
    # The dummy page itself lives on the allow-listed GitHub host; its (mistyped) target host is never contacted.
    assert all("avallibeyaz" not in c for c in calls)
    assert by["reborn-dummy"]["status"] in ("no-redirect-found", "drifted", "matches-registry", "unreachable")


def test_default_probe_refuses_other_hosts_and_reports_offline(monkeypatch):
    import socket

    assert default_probe("https://example.org/", ("avalibeyaz.com",)) == {"ok": False, "error": "host-not-allow-listed"}
    assert default_probe("http://avalibeyaz.com/", ("avalibeyaz.com",))["error"] == "host-not-allow-listed"
    assert default_probe("https://user@avalibeyaz.com/", ("avalibeyaz.com",))["error"] == "host-not-allow-listed"

    def no_dns(*a, **k):
        raise socket.gaierror("no dns")

    monkeypatch.setattr(socket, "getaddrinfo", no_dns)
    assert default_probe("https://avalibeyaz.com/", ("avalibeyaz.com",)) == {"ok": False, "error": "dns"}
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("10.0.0.1", 443))])
    assert default_probe("https://avalibeyaz.com/", ("avalibeyaz.com",))["error"] == "non-public-address"


def test_records_need_confirmation_reject_credentials_and_stay_with_the_phone(tmp_path):
    svc = svc_with(tmp_path, phone())
    body = {"action": "services-record", "device": "usb", "service": "reborn-homepage",
            "before": "https://old.example/", "after": "https://lite.duckduckgo.com", "result": "pass"}
    with pytest.raises(ValueError, match="Confirm"):
        svc.execute(body)
    with pytest.raises(ValueError, match="credentials"):
        svc.execute(dict(body, confirm=True, after="https://user:pw@host/"))
    with pytest.raises(ValueError, match="credentials"):
        svc.execute(dict(body, confirm=True, after="https://host/?token=abc"))
    with pytest.raises(ValueError, match="Invalid result"):
        svc.execute(dict(body, confirm=True, result="works"))
    with pytest.raises(ValueError, match="Unknown service"):
        svc.execute(dict(body, confirm=True, service="x"))
    done = svc.execute(dict(body, confirm=True))["record"]
    assert done["source"] == "manual" and "https://old.example/" in done["restore"]["en"]
    state = svc.execute({"action": "services-state", "device": "usb"})
    assert {s["id"]: s["record"] for s in state["services"]}["reborn-homepage"]["after"] == "https://lite.duckduckgo.com"
    svc.devices.transport.rows = [phone(firmware="other")]
    again = svc.execute({"action": "services-state", "device": "usb"})
    assert {s["id"]: s["record"] for s in again["services"]}["reborn-homepage"] is None


def test_recommendations_are_suggestions_never_actions(tmp_path):
    svc = svc_with(tmp_path, phone())
    facts = svc.facts(svc._row("usb")[0], {"model": "", "rm": "", "firmware": ""})
    recs = svc.services.recommendations(facts)
    assert {r["id"] for r in recs} == {"check-clock-and-tls", "review-endpoints"}
    assert all("install" not in r["action"] for r in recs)
    assert svc.services.recommendations(svc.facts(None, {"model": "", "rm": "", "firmware": ""})) == []


def test_revive_home_lists_suggestions_and_a_deidentified_history(tmp_path):
    svc = svc_with(tmp_path, phone())
    home = svc.execute({"action": "home", "device": "usb"})
    ids = {r["id"] for r in home["recommendations"]}
    assert {"check-clock-and-tls", "review-endpoints", "current-tls-stack", "app-kits"} <= ids
    assert "reborn-hybrid" not in ids  # no recorded support evidence for any N95 variant
    assert {s["id"] for s in home["sections"]} == {"legacy-services", "addons"}
    svc.execute({"action": "services-record", "device": "usb", "service": "reborn-homepage", "before": "SECRET-BEFORE",
                 "after": "https://x.example", "result": "pass", "confirm": True})
    svc.execute({"action": "tls-record", "device": "usb", "item": "mbedtls-lib", "state": "installed", "confirm": True})
    home = svc.execute({"action": "home", "device": "usb"})
    assert "current-tls-stack" not in {r["id"] for r in home["recommendations"]}
    kinds = {(h["kind"], h["item"]) for h in home["history"]}
    assert ("service-setting", "reborn-homepage") in kinds and ("tls", "mbedtls-lib") in kinds
    assert "SECRET-BEFORE" not in str(home) and "x.example" not in str(home)
    assert all(set(h) == {"at", "kind", "item", "result", "source"} for h in home["history"])


def test_revive_home_without_a_phone_is_empty_and_honest(tmp_path):
    home = svc_with(tmp_path).execute({"action": "home"})
    assert home["reason"] == "no-connection" and home["recommendations"] == [] and home["history"] == []
