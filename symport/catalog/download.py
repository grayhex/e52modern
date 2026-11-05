"""Approved-source HTTPS downloader with redirect, address, size and hash checks."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from .packages import MAX_PACKAGE, validate_package

# Only hosts of curated, hash-pinned sources: GitHub releases and the author's own download page for X-plore.
HOSTS = frozenset({'github.com', 'release-assets.githubusercontent.com', 'raw.githubusercontent.com', 'www.lonelycatgames.com'})


def public_https(url: str, resolver=socket.getaddrinfo, hosts=HOSTS) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.port not in (None, 443):
        raise ValueError('Download host is not approved HTTPS')
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Credentials/fragments forbidden in download URLs')
    answers = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not answers or any(not ipaddress.ip_address(answer[4][0]).is_global for answer in answers):
        raise ValueError('Private or non-global download destination rejected')


class Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Downloader:
    def __init__(self, cache: Path, opener=None):
        self.cache = cache
        self.opener = opener or urllib.request.build_opener(Redirects())

    def fetch(self, source: dict, artifact: dict) -> tuple[Path, dict]:
        name = artifact['name']
        if not name or Path(name).name != name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in name):
            raise ValueError('Invalid curated artifact filename')
        expected = artifact['sha256']
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('A curated SHA-256 pin is required')
        if not 0 < artifact['size'] <= MAX_PACKAGE:
            raise ValueError('Artifact exceeds package limit')
        if artifact.get('publisher_sha256') and artifact['publisher_sha256'] != expected:
            raise ValueError('Published SHA-256 differs from the curated pin')
        # Only curated URLs from the source declaration, never URLs received via API.
        if artifact not in source['artifacts']:
            raise ValueError('Artifact not declared by approved source')
        directory = self.cache / expected
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = directory / name
        hit = target.is_file() and not target.is_symlink()
        if hit:
            raw = target.read_bytes()
            hit = len(raw) == artifact['size'] and hashlib.sha256(raw).hexdigest() == expected
        if not hit:
            public_https(artifact['url'])
            start = time.monotonic()
            fd, temporary = tempfile.mkstemp(prefix='.download-', dir=directory)
            try:
                request = urllib.request.Request(artifact['url'], headers={'User-Agent': 'SymPort-AppCatalog/1', 'Accept-Encoding': 'identity'})
                with os.fdopen(fd, 'wb') as output, self.opener.open(request, timeout=20) as response:
                    public_https(response.geturl())
                    length = response.headers.get('Content-Length')
                    if length and int(length) > MAX_PACKAGE:
                        raise ValueError('Download exceeds package limit')
                    total = 0
                    while True:
                        if time.monotonic() - start > 90:
                            raise ValueError('Download time limit exceeded')
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > artifact['size'] or total > MAX_PACKAGE:
                            raise ValueError('Download exceeds curated size')
                        output.write(chunk)
                raw = Path(temporary).read_bytes()
                if len(raw) != artifact['size'] or hashlib.sha256(raw).hexdigest() != expected:
                    raise ValueError('Download size or SHA-256 does not match curated release')
                validate_package(name, raw)
                os.replace(temporary, target)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise ValueError('Approved source unavailable; no package was accepted') from exc
            finally:
                Path(temporary).unlink(missing_ok=True)
        validation = validate_package(name, raw)
        metadata = {'name': name, 'size': len(raw), 'sha256': expected, 'cache_hit': hit,
                    'publisher_sha256': artifact.get('publisher_sha256'), 'validation': validation}
        (directory / (name + '.json')).write_text(json.dumps(metadata, ensure_ascii=False))
        return target, metadata
