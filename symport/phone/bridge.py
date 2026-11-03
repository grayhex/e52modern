"""Capability-based device access. Mounted volumes are never inferred to be phones.

Roots are explicitly enrolled by the operator, not accepted from HTTP clients.
No symlinks, recursive deletion, shell execution or implicit installation.
"""
from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlsplit


class PCBridge:
    """Use an operator-configured loopback SSH tunnel, never a client-supplied URL."""
    def __init__(self, url: str, token: str):
        parsed = urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost'):
            raise ValueError('Bridge requires a loopback SSH tunnel')
        if parsed.path not in ('', '/') or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Invalid bridge URL')
        if len(token) < 32:
            raise ValueError('Bridge key must contain at least 32 characters')
        self.url, self.token = url.rstrip('/') + '/api/bridge', token

    def execute(self, data: dict) -> dict:
        req = urllib.request.Request(self.url, data=json.dumps(data).encode(), headers={
            'Content-Type': 'application/json', 'X-Symport-Bridge-Key': self.token,
            'Host': '127.0.0.1:8765',
        })
        # Never send the local bridge key through an inherited Internet proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        timeout = {'contacts-import': 420, 'contacts-read': 150, 'media-upload': 300, 'discover': 200, 'device-details': 200, 'personal-read': 200, 'personal-preview': 200, 'personal-apply': 1800, 'sms-send': 400}.get(data.get('action'), 30)
        with opener.open(req, timeout=timeout) as response:
            return json.loads(response.read(90 * 1024 * 1024))

    def devices(self) -> list[dict]:
        return self.execute({'action': 'discover'})['devices']


