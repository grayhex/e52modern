"""A deterministic mock of the phone-side agent for tests and demos. Every reply is marked synthetic."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets

from . import protocol as P


class MockAgent:
    def __init__(self, code: str, consent: str = 'granted', tamper: bool = False, version: str = 'mock-0'):
        self.code, self.consent, self.tamper, self.version = code, consent, tamper, version
        self.secret: bytes | None = None
        self.files: dict[str, bytes] = {}
        self.seen: list[str] = []
        self.last_seq = 0

    def send(self, message: dict) -> dict:
        if message.get('type') == 'pair':
            nonce = secrets.token_hex(8)
            self.secret = P.derive_secret(self.code, message['host_nonce'], nonce)
            proof = P.sign(self.secret, {'v': P.VERSION, 'type': 'pair-proof', 'agent_nonce': nonce, 'host_nonce': message['host_nonce']})
            return {'v': P.VERSION, 'agent_nonce': nonce, 'proof': proof}
        body = P.open_message(self.secret, message)
        self.seen.append(body['op'])
        reply = {'v': P.VERSION, 'type': 'reply', 'id': body['id'], 'seq': body['seq'], 'synthetic': True, 'ok': True, 'data': {}}
        op, args = body['op'], body['args']
        spec = P.OPERATIONS[op]
        if spec['consent'] and self.consent != 'granted':
            return P.seal(self.secret, {**reply, 'ok': False, 'consent': 'declined'})
        if op == 'hello':
            reply['data'] = {'agent_version': self.version, 'model': 'Synthetic S60v3', 'platform': 'S60 3rd FP1', 'abi': 'armv5', 'synthetic': True}
        elif op == 'ping':
            reply['data'] = {'pong': True}
        elif op == 'sys.memory':
            reply['data'] = {'ram_free': 1000, 'ram_total': 2000, 'rom_free': 3, 'imei': '000000000000000'}
        elif op == 'sys.battery':
            reply['data'] = {'percent': 80, 'charging': False}
        elif op == 'sys.patches':
            reply['data'] = {'patches': [{'name': 'Synthetic patch', 'state': 'applied'}], 'secret_token': 'must-be-dropped'}
        elif op == 'net.test':
            reply['data'] = {'reachable': True, 'ms': 120}
        elif op in ('file.echo-test', 'file.send'):
            raw = base64.b64decode(args['content'])
            self.files[args['path']] = raw
            stored = raw[:-1] + b'X' if self.tamper else raw
            reply['read_back_sha256'] = hashlib.sha256(stored).hexdigest()
        elif op == 'export.contacts':
            payload = json.dumps({'rows': [{k: 'x' for k in args['fields']}]}).encode()
            reply['payload'] = base64.b64encode(payload).decode()
            reply['payload_sha256'] = hashlib.sha256(payload + (b'!' if self.tamper else b'')).hexdigest()
        elif op == 'install.open':
            reply['data'] = {'opened': True}
        else:
            reply['ok'] = False
            reply['error'] = 'not implemented by the mock'
        return P.seal(self.secret, reply)
