"""Private phone-file endpoint used by the file browser: session cookie, Fetch Metadata and untrusted content."""
from __future__ import annotations

import http.client
import json

import pytest

from symport.web import Workbench, make_handler  # noqa: F401
from tests.test_web import http_server, repo  # noqa: F401


@pytest.fixture
def volume(tmp_path, monkeypatch):
    root = tmp_path / "card"
    root.mkdir()
    (root / "note.txt").write_text("private bytes")
    (root / "page.html").write_text("<script>alert(1)</script>")
    (root / "icon.svg").write_text("<svg onload='alert(1)'/>")
    (root / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
    (root / "app.sis").write_bytes(b"sis bytes")
    monkeypatch.setenv("SYMPORT_DEVICE_ROOTS", json.dumps({"card": str(root)}))
    return root


def get(port, path, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path, headers={"Host": f"127.0.0.1:{port}", **(headers or {})})
    response = conn.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    conn.close()
    return result


def test_requires_the_session_cookie_and_rejects_cross_site(repo, volume, http_server):  # noqa: F811
    state, port = http_server
    path = "/api/device/file?device=card&path=note.txt"
    assert get(port, path)[0] == 403
    assert get(port, path, {"Cookie": "symport_media=wrong"})[0] == 403
    cookie = {"Cookie": f"symport_media={state.token}"}
    assert get(port, path, {**cookie, "Sec-Fetch-Site": "cross-site"})[0] == 403
    assert get(port, path, {**cookie, "Host": "evil.example"})[0] == 403
    assert get(port, path, cookie)[0] == 200


def test_embedded_loads_are_inline_but_navigation_is_a_download(repo, volume, http_server):  # noqa: F811
    state, port = http_server
    cookie = {"Cookie": f"symport_media={state.token}"}
    path = "/api/device/file?device=card&path=note.txt"
    status, headers, body = get(port, path, {**cookie, "Sec-Fetch-Dest": "empty"})
    assert status == 200 and body == b"private bytes"
    assert headers["Content-Disposition"].startswith("inline") and headers["Content-Type"].startswith("text/plain")
    assert get(port, path, {**cookie, "Sec-Fetch-Dest": "document"})[1]["Content-Disposition"].startswith("attachment")
    assert get(port, path, cookie)[1]["Content-Disposition"].startswith("attachment")        # no Fetch Metadata
    assert get(port, path + "&download=1", {**cookie, "Sec-Fetch-Dest": "empty"})[1]["Content-Disposition"].startswith("attachment")


def test_untrusted_content_cannot_run_or_be_sniffed(repo, volume, http_server):  # noqa: F811
    state, port = http_server
    cookie = {"Cookie": f"symport_media={state.token}", "Sec-Fetch-Dest": "iframe"}
    status, headers, _ = get(port, "/api/device/file?device=card&path=page.html", cookie)
    assert status == 200 and "sandbox" in headers["Content-Security-Policy"] and headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert headers["X-Content-Type-Options"] == "nosniff" and "frame-ancestors 'self'" in headers["Content-Security-Policy"]
    status, headers, _ = get(port, "/api/device/file?device=card&path=icon.svg", cookie)
    assert headers["Content-Type"] == "application/octet-stream" and headers["Content-Disposition"].startswith("attachment")
    status, headers, _ = get(port, "/api/device/file?device=card&path=app.sis", cookie)
    assert headers["Content-Type"] == "application/octet-stream"
    assert get(port, "/api/device/file?device=card&path=photo.png", cookie)[1]["Content-Type"] == "image/png"


def test_range_paths_and_unknown_files_are_handled(repo, volume, http_server):  # noqa: F811
    state, port = http_server
    cookie = {"Cookie": f"symport_media={state.token}", "Sec-Fetch-Dest": "video"}
    status, headers, body = get(port, "/api/device/file?device=card&path=note.txt", {**cookie, "Range": "bytes=0-6"})
    assert status == 206 and body == b"private" and headers["Content-Range"] == "bytes 0-6/13"
    assert get(port, "/api/device/file?device=card&path=note.txt", {**cookie, "Range": "bytes=99-"})[0] == 416
    for bad in ("../outside", "missing.txt", "..%2F..%2Fetc%2Fpasswd"):
        assert get(port, f"/api/device/file?device=card&path={bad}", cookie)[0] == 400
    assert get(port, "/api/device/file?device=nope&path=note.txt", cookie)[0] == 400
