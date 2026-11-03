"""Test-only MGO contract double. No EKA2L1/phone compatibility evidence."""
from __future__ import annotations

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from PIL import Image, ImageDraw

from symport.lab.client import AgentError
from symport.sis.writer import SisFile, SisPackage, build

TOKEN = 'test-only-mgo-contract-token'


def sis(theme=False):
    target = '!:\\resource\\skins\\e0000001\\fixture.skn' if theme else '!:\\sys\\bin\\fixture.exe'
    return build(SisPackage(0xE0000001, 'Contract fixture', 'Test', files=[SisFile(target, b'TEST ONLY')]))


def screen():
    image = Image.new('RGB', (240, 320), '#082f49')
    ImageDraw.Draw(image).text((20, 140), 'TEST DOUBLE\nNot an emulator result', fill='#22d3ee')
    output = io.BytesIO()
    image.save(output, 'PNG')
    return output.getvalue()


class MockMgo:
    def __init__(self, installed=True):
        self.calls, self.uploads = [], []
        self.installed, self.running, self.save_key = installed, False, None
        self.default = 'mock-device' if installed else None
        self.fail_install, self.launch_state, self.added = False, 'running', [{'uid': '0xe0000001', 'name': 'Fixture'}]
        self.registry = []
        self.png = screen()
        self.job_failure = None

    def upload(self, route, name, stream, length, bundle=None):
        raw = stream.read(length)
        if len(raw) != length:
            raise AgentError('Upload truncated', code='upload-interrupted')
        self.uploads.append(dict(route=route, name=name, raw=raw, bundle=bundle))
        return {'file': name, 'path': '/data/run/mock/in/' + name}

    def request(self, method, path, body=None, **kwargs):
        self.calls.append((method, path, body))
        if path == '/agent/health':
            return {'ok': True, 'emulator': 'MGO CONTRACT DOUBLE — NOT EKA2L1',
                    'firmware': {'installed': self.installed, 'devices': [{'code': 'mock-device', 'manufacturer': 'Mock', 'model': 'Contract fixture'}] if self.installed else []},
                    'defaults': {'symbian': self.default}, 'instance': {'running': self.running, 'saveKey': self.save_key}}
        if path == '/agent/instance':
            self.running = method == 'POST'
            self.save_key = (body or {}).get('saveKey')
            return {'id': 'mock-instance'}
        if path == '/agent/defaults':
            if body['code'] != 'mock-device' or not self.installed:
                raise AgentError('Unknown device', 404, 'not_found')
            self.default = body['code']
            return {'defaults': {'symbian': self.default}}
        if path == '/agent/firmware/install':
            return {'id': 'a' * 12, 'kind': 'install_device', 'state': 'running'}
        if path.startswith('/agent/jobs/'):
            self.installed = not self.job_failure
            return {'id': 'a' * 12, 'state': 'failed' if self.job_failure else 'succeeded', 'error': self.job_failure}
        if path == '/agent/log':
            return {'agent': ['contract test double'], 'output': [], 'eka2l1Log': [], 'live': self.running}
        if path == '/v1/screenshot?region=guest':
            if not self.running:
                raise AgentError('no active emulator surface', 409, 'no_screen')
            return self.png
        if path == '/v1/status':
            return {'started': self.running, 'device': {'code': self.default}}
        if path == '/v1/devices':
            return {'current': {'code': self.default}}
        if path.startswith('/v1/devices/'):
            return {'ok': True}
        if path == '/v1/apps':
            if method == 'POST':
                if self.fail_install:
                    raise AgentError('Installer rejected test SIS', 422, 'install_failed')
                self.registry = self.added
                return {'added': self.added}
            return {'apps': self.registry}
        if path.endswith('/launch'):
            return {'state': self.launch_state, 'screenVisible': self.launch_state == 'running'}
        if path == '/v1/session':
            return {'state': self.launch_state}
        if path == '/v1/keys':
            return {'keys': {k: 'test' for k in ['up', 'down', 'left', 'right', 'ok', 'applications', 'lsk', 'rsk', 'clear', 'end', 'call', 'star', 'hash', *'0123456789']}}
        if path == '/v1/capabilities':
            return {'firmwareFormats': ['rom', 'rpkg', 'archive', 'vpl']}
        if path in ('/v1/input/key', '/v1/input/release'):
            return {'ok': True}
        raise AssertionError(f'Unexpected MGO call: {method} {path}')


def serve_mock(agent, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_request(self):
            if self.headers.get('Authorization') != 'Bearer ' + TOKEN:
                return self.respond(401, {'error': {'code': 'unauthorized', 'message': 'Unauthorized'}})
            url = urlsplit(self.path)
            try:
                if self.command == 'PUT' and (url.path.startswith('/agent/firmware/') or url.path == '/agent/upload/package'):
                    args = parse_qs(url.query)
                    result = agent.upload(url.path, args['name'][0], self.rfile, int(self.headers['Content-Length']), args.get('bundle', [None])[0])
                else:
                    length = int(self.headers.get('Content-Length', '0'))
                    result = agent.request(self.command, self.path, json.loads(self.rfile.read(length)) if length else None)
                self.respond(200, result)
            except AgentError as exc:
                self.respond(exc.status or 503, {'error': {'code': exc.code, 'message': str(exc)}})

        def respond(self, status, value):
            raw = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'image/png' if isinstance(value, bytes) else 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        do_GET = do_POST = do_PUT = do_DELETE = handle_request

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
