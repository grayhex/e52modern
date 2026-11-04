"""Bridge update trust model: signed manifest, strict URLs, hash-checked download, no downgrade."""
import base64
import hashlib
import io
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from symport.bridge import ed25519, update
from symport.bridge.update import UpdateError

RFC8032_1 = dict(
    public="d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    message=b"",
    signature=bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    ),
)


def test_ed25519_matches_rfc_vector_and_rejects_tampering():
    public = bytes.fromhex(RFC8032_1["public"])
    assert ed25519.verify(public, RFC8032_1["message"], RFC8032_1["signature"])
    assert not ed25519.verify(public, b"x", RFC8032_1["signature"])
    flipped = bytearray(RFC8032_1["signature"])
    flipped[10] ^= 1
    assert not ed25519.verify(public, b"", bytes(flipped))
    assert not ed25519.verify(public[:31], b"", RFC8032_1["signature"])
    assert not ed25519.verify(public, b"", RFC8032_1["signature"][:63])


def test_ed25519_agrees_with_cryptography():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    for message in (b"a", b"manifest" * 100, bytes(range(256))):
        assert ed25519.verify(public, message, key.sign(message))
        assert not ed25519.verify(public, message + b"!", key.sign(message))


def manifest(version="0.3.0", **changes):
    name = f"SymPortBridge-Setup-{version}.exe"
    data = {
        "schema": update.SCHEMA,
        "version": version,
        "released": "2026-11-04",
        "notes": "Installer",
        "installer": {
            "name": name,
            "url": f"https://github.com/{update.REPO}/releases/download/bridge-v{version}/{name}",
            "size": 5000,
            "sha256": "a" * 64,
        },
    }
    data.update(changes)
    return data


def sign(data, key):
    return dict(data, signature=base64.b64encode(key.sign(update.canonical(data))).decode())


def test_newer_valid_manifest_is_offered_older_or_equal_is_not():
    assert update.validate_manifest(manifest("0.3.0"), "0.2.0", "").version == "0.3.0"
    assert update.validate_manifest(manifest("0.2.0"), "0.2.0", "") is None
    assert update.validate_manifest(manifest("0.1.9"), "0.2.0", "") is None
    assert update.validate_manifest(manifest("0.10.0"), "0.9.9", "") is not None  # numeric, not text order


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m["installer"].update(url="https://evil.example/SymPortBridge-Setup-0.3.0.exe"),
        lambda m: m["installer"].update(url=m["installer"]["url"].replace(update.REPO, "other/repo")),
        lambda m: m["installer"].update(url=m["installer"]["url"].replace("bridge-v0.3.0", "bridge-v0.2.9")),
        lambda m: m["installer"].update(url=m["installer"]["url"].replace("https", "http")),
        lambda m: m["installer"].update(name="Setup.exe"),
        lambda m: m["installer"].update(name="SymPortBridge-Setup-0.2.9.exe"),
        lambda m: m["installer"].update(sha256="xyz"),
        lambda m: m["installer"].update(size=-1),
        lambda m: m["installer"].update(size=update.MAX_INSTALLER + 1),
        lambda m: m.update(schema="other"),
        lambda m: m.update(version="latest"),
        lambda m: m.pop("installer"),
    ],
)
def test_malformed_or_foreign_manifests_are_rejected(mutate):
    data = manifest()
    mutate(data)
    with pytest.raises(UpdateError):
        update.validate_manifest(data, "0.2.0", "")


def test_signature_is_required_once_a_key_is_configured():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    good = sign(manifest(), key)
    assert update.validate_manifest(good, "0.2.0", public).signed is True
    with pytest.raises(UpdateError, match="signature"):
        update.validate_manifest(manifest(), "0.2.0", public)  # unsigned
    tampered = json.loads(json.dumps(good))
    tampered["installer"]["sha256"] = "b" * 64
    with pytest.raises(UpdateError, match="signature"):
        update.validate_manifest(tampered, "0.2.0", public)
    other = Ed25519PrivateKey.generate()
    with pytest.raises(UpdateError, match="signature"):
        update.validate_manifest(sign(manifest(), other), "0.2.0", public)
    with pytest.raises(UpdateError, match="signature"):
        update.validate_manifest(dict(good, signature="not base64!"), "0.2.0", public)


def release(tag, manifest_url="https://github.com/x/releases/download/t/bridge-update.json", **extra):
    return dict(
        tag_name=tag,
        draft=False,
        prerelease=False,
        assets=[dict(name=update.MANIFEST_NAME, browser_download_url=manifest_url)],
        **extra,
    )


def fetcher(releases, manifests):
    def fetch(url, limit=0):
        if url == update.RELEASES_URL:
            return json.dumps(releases).encode()
        return json.dumps(manifests[url]).encode()

    return fetch


def test_latest_release_selection_ignores_drafts_prereleases_and_foreign_tags():
    base = "https://github.com/x/releases/download/{}/bridge-update.json"
    releases = [
        release("v9.9.9"),  # image release, not a Bridge
        dict(release("bridge-v0.9.0"), prerelease=True),
        dict(release("bridge-v0.8.0"), draft=True),
        release("bridge-v0.3.0", base.format("a")),
        release("bridge-v0.10.0", base.format("b")),
        release("bridge-v0.4.0-rc1"),
    ]
    manifests = {base.format("a"): manifest("0.3.0"), base.format("b"): manifest("0.10.0")}
    found = update.check("0.2.0", fetcher(releases, manifests), "")
    assert found is not None and found.version == "0.10.0"


def test_no_bridge_release_means_no_update():
    assert update.check("0.2.0", fetcher([release("v1.0.0")], {}), "") is None
    assert update.check("0.2.0", fetcher([], {}), "") is None


def test_manifest_must_describe_its_own_release():
    url = "https://github.com/x/releases/download/t/bridge-update.json"
    with pytest.raises(UpdateError, match="match"):
        update.check("0.2.0", fetcher([release("bridge-v0.3.0", url)], {url: manifest("0.4.0")}), "")


def test_unexpected_hosts_are_refused_before_any_request():
    for url in ("http://github.com/x", "https://evil.example/x", "https://github.com.evil.example/x",
                "https://user@github.com/x", "https://github.com:8443/x"):
        assert not update.host_allowed(url)
        with pytest.raises(UpdateError):
            update.default_fetch(url)
    assert update.host_allowed("https://objects.githubusercontent.com/a/b")


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Opener:
    def __init__(self, payload):
        self.payload = payload

    def open(self, request, timeout=None):
        return Response(self.payload)


def make_update(payload, **changes):
    base = update.validate_manifest(
        manifest(
            installer={
                "name": "SymPortBridge-Setup-0.3.0.exe",
                "url": f"https://github.com/{update.REPO}/releases/download/bridge-v0.3.0/SymPortBridge-Setup-0.3.0.exe",
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ),
        "0.2.0",
        "",
    )
    return base if not changes else update.Update(**{**base.__dict__, **changes})


def test_download_publishes_the_file_only_after_size_and_hash_match(tmp_path):
    payload = b"MZ" + b"installer" * 500
    seen = []
    path = update.download(make_update(payload), tmp_path, lambda a, b: seen.append((a, b)), Opener(payload))
    assert path.read_bytes() == payload and seen[-1] == (len(payload), len(payload))
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("served", [b"MZ" + b"x" * 4000, b"MZ" + b"installer" * 400, b"MZ" + b"installer" * 600])
def test_corrupt_short_or_oversized_download_leaves_nothing_behind(tmp_path, served):
    payload = b"MZ" + b"installer" * 500
    with pytest.raises(UpdateError):
        update.download(make_update(payload), tmp_path, opener=Opener(served))
    assert list(tmp_path.iterdir()) == []


def test_check_cadence_and_install_detection(monkeypatch):
    assert update.due(None) and not update.due(1000.0, 1000.0 + 3600) and update.due(1000.0, 1000.0 + 90000)
    assert update.installed() is False  # not a frozen installation


class Flow:
    """Drive run_flow with fakes and record what the user would have seen."""

    def __init__(self, tmp_path, answer=True, idle=True, installed=True, found=True):
        self.root, self.answer, self.idle_value, self.is_installed = tmp_path, answer, idle, installed
        self.asked, self.told, self.notes, self.launched, self.downloads = [], [], [], [], []
        payload = b"MZ" + b"installer" * 500
        self.payload = payload
        self.update = make_update(payload) if found else None

    def run(self, interactive=True, fail_check=False):
        def fetch(url, limit=0):
            if fail_check:
                raise UpdateError("The update server could not be reached")
            if self.update is None:
                return b"[]"
            if url == update.RELEASES_URL:
                return json.dumps([release("bridge-v0.3.0", "https://github.com/x/releases/download/t/bridge-update.json")]).encode()
            return json.dumps(manifest(installer={
                "name": self.update.name, "url": self.update.url, "size": self.update.size, "sha256": self.update.sha256,
            })).encode()

        def downloader(found, directory):
            self.downloads.append(found.version)
            return update.download(found, directory, opener=Opener(self.payload))

        return update.run_flow(
            self.root, interactive=interactive, ask=lambda t: self.asked.append(t) or self.answer,
            inform=self.told.append, notify=self.notes.append, fetch=fetch, public_key="",
            downloader=downloader, idle=lambda: self.idle_value, launch=self.launched.append,
            is_installed=lambda: self.is_installed, current="0.2.0",
        )


def test_flow_asks_before_downloading_and_launches_only_after_consent(tmp_path):
    flow = Flow(tmp_path)
    assert flow.run() == "launched"
    assert "0.3.0" in flow.asked[0] and "SHA-256" in flow.asked[0] and "checksum only" in flow.asked[0]
    assert flow.launched[0].read_bytes() == flow.payload


def test_declining_downloads_and_installs_nothing(tmp_path):
    flow = Flow(tmp_path, answer=False)
    assert flow.run() == "declined"
    assert flow.downloads == [] and flow.launched == []


def test_automatic_pass_only_notifies_once_and_never_downloads(tmp_path):
    flow = Flow(tmp_path)
    assert flow.run(interactive=False) == "notified"
    assert flow.run(interactive=False) == "already-notified"
    assert len(flow.notes) == 1 and flow.downloads == [] and flow.asked == [] and flow.launched == []
    assert update.load_state(tmp_path)["last_check"]


def test_running_phone_operation_blocks_the_installer(tmp_path):
    flow = Flow(tmp_path, idle=False)
    assert flow.run() == "busy"
    assert flow.launched == [] and "phone operation" in flow.told[0]


def test_portable_copy_points_to_releases_instead_of_installing(tmp_path):
    flow = Flow(tmp_path, installed=False)
    assert flow.run() == "portable" and flow.asked == [] and flow.downloads == []


def test_errors_and_up_to_date_are_reported_only_when_the_user_asked(tmp_path):
    assert Flow(tmp_path, found=False).run() == "up-to-date"
    quiet = Flow(tmp_path)
    assert quiet.run(interactive=False, fail_check=True) == "error" and quiet.told == []
    loud = Flow(tmp_path)
    assert loud.run(fail_check=True) == "error" and "could not be reached" in loud.told[0]


def load_key_tool():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "update_key", Path(__file__).parents[1] / "tools/windows/update_key.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_signing_tool_produces_what_the_bridge_accepts(tmp_path, monkeypatch, capsys):
    tool = load_key_tool()
    assert tool.main(["generate"]) == 0
    out = capsys.readouterr().out
    public = out.split("PUBLIC (set UPDATE_PUBLIC_KEY in symport/bridge/update.py): ")[1].split()[0]
    seed = out.split("never commit): ")[1].split()[0]
    path = tmp_path / "bridge-update.json"
    path.write_text(json.dumps(manifest()))
    # Without a configured public key an unsigned manifest is tolerated; with one it is mandatory.
    monkeypatch.delenv("BRIDGE_UPDATE_SIGNING_KEY", raising=False)
    assert tool.main(["sign", str(path)]) == 0
    monkeypatch.setattr(update, "UPDATE_PUBLIC_KEY", public)
    assert tool.main(["sign", str(path)]) == 1
    monkeypatch.setenv("BRIDGE_UPDATE_SIGNING_KEY", seed)
    assert tool.main(["sign", str(path)]) == 0
    signed = json.loads(path.read_text())
    assert update.validate_manifest(signed, "0.2.0", public).signed
    monkeypatch.setenv("BRIDGE_UPDATE_SIGNING_KEY", base64.b64encode(Ed25519PrivateKey.generate().private_bytes_raw()).decode())
    assert tool.main(["sign", str(path)]) == 1  # a key that does not match the embedded public key
