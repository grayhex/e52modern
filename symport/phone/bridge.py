"""Capability-based device access. Mounted volumes are never inferred to be phones.

Roots are explicitly enrolled by the operator, not accepted from HTTP clients.
No symlinks, recursive deletion, shell execution or implicit installation.
"""
from __future__ import annotations

import json
import os
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
        self.last_connections = []
        self.url, self.token = url.rstrip('/') + '/api/bridge', token

    def execute(self, data: dict) -> dict:
        req = urllib.request.Request(self.url, data=json.dumps(data).encode(), headers={
            'Content-Type': 'application/json', 'X-Symport-Bridge-Key': self.token,
            'Host': '127.0.0.1:' + str(int(os.getenv('SYMPORT_BRIDGE_AGENT_PORT', '8765'))),
        })
        # Never send the local bridge key through an inherited Internet proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        timeout = {'contacts-import': 420, 'contacts-read': 150, 'media-upload': 300, 'discover': 200, 'device-details': 200, 'personal-read': 200, 'personal-preview': 200, 'personal-apply': 1800, 'sms-send': 400, 'connection-diagnose': 200, 'upload': 300, 'software-transfer': 300, 'transfer': 300, 'download': 150}.get(data.get('action'), 30)
        with opener.open(req, timeout=timeout) as response:
            return json.loads(response.read(90 * 1024 * 1024))

    def devices(self) -> list[dict]:
        data = self.execute({'action': 'discover'})
        self.last_connections = data.get('connections', [])
        return data['devices']

    def diagnostics(self):
        return self.last_connections


