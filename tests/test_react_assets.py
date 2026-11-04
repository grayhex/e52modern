"""Static React entry keeps the existing host, CSP and private-session boundaries."""
from __future__ import annotations

import http.client

from tests.test_web import _http, http_server, repo  # noqa: F401


def test_react_default_static_and_session(http_server, tmp_path, monkeypatch):  # noqa: F811
    from symport import web

    state, port = http_server
    assets = tmp_path / 'react'
    (assets / 'assets').mkdir(parents=True)
    (assets / 'index.html').write_text('<meta name="symport-token" content="__SESSION_TOKEN__"><script src="/next/assets/main.js"></script>')
    (assets / 'assets/main.js').write_text('/* independent static client */')
    monkeypatch.setattr(web, 'REACT_ASSETS', assets)
    monkeypatch.setenv('SYMPORT_FRONTEND', 'react')
    conn = http.client.HTTPConnection('127.0.0.1', port)
    conn.request('GET', '/')
    response = conn.getresponse()
    body = response.read()
    assert response.status == 200 and state.token.encode() in body
    assert b'/next/assets/main.js' in body and b'/app.js' not in body
    assert 'HttpOnly' in response.getheader('Set-Cookie')
    assert 'default-src' in response.getheader('Content-Security-Policy')
    conn.close()
    assert _http(port, 'GET', '/next/assets/main.js') == (200, b'/* independent static client */')
    assert _http(port, 'GET', '/next/assets/main.js', headers={'Host': 'evil.test'})[0] == 403
    for path in ('/next/../private', '/next/%2e%2e/private', '/next/assets/missing.js'):
        assert _http(port, 'GET', path)[0] == 404
    private = tmp_path / 'private.js'
    private.write_text('private bytes')
    (assets / 'assets/private.js').symlink_to(private)
    assert _http(port, 'GET', '/next/assets/private.js')[0] == 404
    monkeypatch.setenv('SYMPORT_FRONTEND', 'classic')
    assert b'/app.js' in _http(port, 'GET', '/')[1]
    assert b'/app.js' in _http(port, 'GET', '/classic')[1]
    assert state.token.encode() in _http(port, 'GET', '/next/')[1]
