"""Host side of the Device Agent: pairing, per-operation permissions, authenticated calls, honest levels.

Everything is in memory: after a restart the phone must be paired again and every permission is
gone. The transport is injected (the Windows Bridge in the future, a mock in tests); with none the
agent is ``not-installed`` and every call is refused. Results carry three separate levels:
``agent-connected`` (an authenticated reply arrived), ``operation-completed`` (the agent says it
did it) and ``device-verified`` (evidence the host checked itself: a read-back or payload hash).
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
from collections.abc import Callable

from . import protocol as P

GRANT_SECONDS = 3600
FOLDER = re.compile(r'^SymPort-[A-Za-z0-9-]{1,40}/[A-Za-z0-9._-]{1,80}$')
READ_KEYS = {  # data minimisation: only these keys of a read reply are kept
    'sys.memory': ('ram_free', 'ram_total', 'rom_free'), 'sys.battery': ('percent', 'charging'), 'sys.signal': ('bars',),
    'sys.processes': ('processes',), 'sys.packages': ('packages',), 'sys.runtime': ('runtimes',), 'sys.patches': ('patches',),
    'net.test': ('reachable', 'ms'), 'log.tail': ('lines',), 'ping': ('pong',),
}


class AgentHost:
    def __init__(self, transport=None, journal: Callable[[str, str], None] | None = None, clock=time.monotonic):
        self.transport = transport
        self.journal = journal or (lambda action, status: None)
        self.clock = clock
        self.secret: bytes | None = None
        self.pending: dict | None = None
        self.grants: dict[str, float] = {}
        self.counter = 0
        self.agent_info: dict | None = None

    # ---- state -----------------------------------------------------------------------------------------
    def state(self) -> dict:
        now = self.clock()
        status = ('not-installed' if self.transport is None else 'paired' if self.secret else 'pairing' if self.pending else 'not-paired')
        return {'protocol': P.VERSION, 'status': status, 'agent_binary': 'not-built-in-this-change' if self.transport is None else 'present',
                'levels': list(P.LEVELS), 'agent': self.agent_info,
                'permissions': {p: max(0, int(self.grants.get(p, 0) - now)) for p in P.PERMISSIONS},
                'operations': {k: {kk: v[kk] for kk in ('tier', 'permission', 'consent', 'evidence')} for k, v in P.OPERATIONS.items()},
                'forbidden': list(P.FORBIDDEN),
                'statement': 'Optional and opt-in. No generic system write, shell or automatic jailbreak exists. Without the agent every other function works as before.'}

    # ---- pairing ---------------------------------------------------------------------------------------
    def pair_start(self) -> dict:
        if self.transport is None:
            raise ValueError('The Device Agent is not installed: no agent transport exists in this build')
        self.secret = None
        self.pending = {'code': P.new_code(), 'nonce': secrets.token_hex(8), 'expires': self.clock() + P.PAIRING_TTL}
        return {'code': self.pending['code'], 'expires_in': P.PAIRING_TTL,
                'instruction': 'Enter this code in the SymPort agent on the phone. It is shown once and never stored.'}

    def pair_finish(self) -> dict:
        if not self.pending or self.pending['expires'] < self.clock():
            self.pending = None
            raise ValueError('Start pairing again: the code expired')
        reply = self.transport.send({'v': P.VERSION, 'type': 'pair', 'host_nonce': self.pending['nonce']})
        secret = P.derive_secret(self.pending['code'], self.pending['nonce'], str(reply.get('agent_nonce', '')))
        proof = P.sign(secret, {'v': P.VERSION, 'type': 'pair-proof', 'agent_nonce': str(reply.get('agent_nonce', '')), 'host_nonce': self.pending['nonce']})
        if reply.get('proof') != proof or reply.get('v') != P.VERSION:
            self.pending = None
            self.journal('agent-pair', 'failed')
            raise ValueError('Pairing failed: the phone did not prove it knows the code')
        self.secret, self.pending, self.counter = secret, None, 0
        hello = self.call('hello', {})
        self.agent_info = {k: hello['data'].get(k) for k in ('agent_version', 'model', 'platform', 'abi', 'synthetic')}
        self.journal('agent-pair', 'success')
        return {'status': 'paired', 'agent': self.agent_info, 'levels': hello['levels']}

    def disconnect(self) -> dict:
        self.secret, self.pending, self.agent_info = None, None, None
        self.grants.clear()
        self.journal('agent-disconnect', 'success')
        return {'status': 'disconnected'}

    # ---- permissions -----------------------------------------------------------------------------------
    def grant(self, permission: str, seconds: int = GRANT_SECONDS) -> dict:
        if permission not in P.PERMISSIONS:
            raise ValueError('Unknown permission')
        if not self.secret:
            raise ValueError('Pair the agent first')
        seconds = max(60, min(int(seconds), GRANT_SECONDS))
        self.grants[permission] = self.clock() + seconds
        self.journal('agent-grant', 'success')
        return {'permission': permission, 'expires_in': seconds}

    def revoke(self, permission: str | None = None) -> dict:
        if permission is None:
            self.grants.clear()
        elif permission in self.grants:
            del self.grants[permission]
        else:
            raise ValueError('That permission is not granted')
        self.journal('agent-revoke', 'success')
        return {'revoked': permission or 'all'}

    # ---- calls -----------------------------------------------------------------------------------------
    def call(self, op: str, args: dict | None = None, confirm: bool = False) -> dict:
        if op in P.FORBIDDEN or any(op.startswith(f) for f in P.FORBIDDEN):
            raise ValueError('This operation is forbidden by design')
        spec = P.OPERATIONS.get(op)
        if spec is None:
            raise ValueError('Unknown agent operation')
        if self.transport is None or not self.secret:
            raise ValueError('The agent is not paired')
        if spec['permission'] and self.grants.get(spec['permission'], 0) <= self.clock():
            raise ValueError(f"Permission {spec['permission']} is not granted (or expired)")
        if spec['tier'] == 'confirmed' and confirm is not True:
            raise ValueError('Confirm this action; the phone will also ask for your consent')
        args = self._check_args(op, args or {})
        self.counter += 1
        request = P.seal(self.secret, {'v': P.VERSION, 'type': 'call', 'id': secrets.token_hex(6), 'seq': self.counter, 'op': op, 'args': args})
        reply = P.open_message(self.secret, self.transport.send(request))
        if reply.get('id') != request['id'] or reply.get('seq') != self.counter:
            raise ValueError('The agent reply does not match the request (replay or mix-up)')
        levels = {'agent-connected': True, 'operation-completed': False, 'device-verified': False}
        result = {'op': op, 'levels': levels, 'synthetic': bool(reply.get('synthetic'))}
        if reply.get('consent') == 'declined':
            result.update(status='declined-on-phone', data={})
            self.journal('agent-' + op, 'declined')
            return result
        if not reply.get('ok'):
            result.update(status='failed', data={}, error=str(reply.get('error', ''))[:200])
            self.journal('agent-' + op, 'failed')
            return result
        levels['operation-completed'] = True
        data = reply.get('data') if isinstance(reply.get('data'), dict) else {}
        if op in READ_KEYS:
            data = {k: data[k] for k in READ_KEYS[op] if k in data}
        verified = self._verify(op, args, reply)
        levels['device-verified'] = verified is True
        result.update(status='completed', data=data, verification=verified if verified is not None else 'not-applicable')
        self.journal('agent-' + op, 'success')
        return result

    @staticmethod
    def _check_args(op: str, args: dict) -> dict:
        if op in ('file.echo-test', 'file.send'):
            path = args.get('path')
            if not isinstance(path, str) or not FOLDER.fullmatch(path):
                raise ValueError('The agent writes only inside a SymPort-* folder, with a plain file name')
            try:
                raw = base64.b64decode(args.get('content', ''), validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError('Invalid content') from exc
            if not 0 < len(raw) <= 64 * 1024:
                raise ValueError('The agent transfers at most 64 KiB')
            return {'path': path, 'content': args['content']}
        if op == 'install.open':
            path = args.get('path')
            if not isinstance(path, str) or not FOLDER.fullmatch(path):
                raise ValueError('The installer is opened only for a file inside a SymPort-* folder')
            return {'path': path}
        if op == 'export.contacts':
            fields = args.get('fields', ['name', 'numbers'])
            if not isinstance(fields, list) or not set(fields) <= {'name', 'numbers', 'emails'}:
                raise ValueError('Choose only name, numbers or emails')
            return {'fields': sorted(set(fields))}
        if op == 'net.test':
            host = args.get('host')
            if not isinstance(host, str) or not re.fullmatch(r'[a-z0-9.-]{3,80}', host):
                raise ValueError('Enter a host name')
            return {'host': host}
        return {}

    @staticmethod
    def _verify(op: str, args: dict, reply: dict):
        if op in ('file.echo-test', 'file.send'):
            expected = hashlib.sha256(base64.b64decode(args['content'])).hexdigest()
            return reply.get('read_back_sha256') == expected
        if op == 'export.contacts':
            payload = reply.get('payload')
            return isinstance(payload, str) and reply.get('payload_sha256') == hashlib.sha256(base64.b64decode(payload)).hexdigest()
        return None
