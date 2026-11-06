"""SymPort Device Agent protocol ``symport.agent/1`` (host side).

An optional agent on an S60v3 phone would add read-only diagnostics and a few user-visible,
individually permitted actions. No agent binary exists in this change: this module is the versioned
contract, the authentication and the permission model, exercised against a mock. A message is an
HMAC-SHA256-authenticated JSON envelope; every operation has a tier (``read`` or ``confirmed``), a
permission id and, for confirmed ones, a visible consent on the phone. There is no generic system
write, no shell and no automatic jailbreak, and none can be added by a client message: unknown
operations are refused by the host before anything is sent.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets

VERSION = 'symport.agent/1'
PAIRING_TTL = 120
MAX_MESSAGE = 64 * 1024

# op -> tier, permission, phone consent, evidence the agent can return, what it may NOT do
OPERATIONS: dict[str, dict] = {
    'hello': {'tier': 'read', 'permission': None, 'consent': False, 'evidence': 'authenticated-reply'},
    'capabilities': {'tier': 'read', 'permission': None, 'consent': False, 'evidence': 'self-report'},
    'ping': {'tier': 'read', 'permission': None, 'consent': False, 'evidence': 'round-trip'},
    'sys.memory': {'tier': 'read', 'permission': 'diagnostics.read', 'consent': False, 'evidence': 'api-reading'},
    'sys.battery': {'tier': 'read', 'permission': 'diagnostics.read', 'consent': False, 'evidence': 'api-reading'},
    'sys.signal': {'tier': 'read', 'permission': 'diagnostics.read', 'consent': False, 'evidence': 'api-reading'},
    'sys.processes': {'tier': 'read', 'permission': 'processes.read', 'consent': False, 'evidence': 'api-reading'},
    'sys.packages': {'tier': 'read', 'permission': 'packages.read', 'consent': False, 'evidence': 'registry-reading'},
    'sys.runtime': {'tier': 'read', 'permission': 'diagnostics.read', 'consent': False, 'evidence': 'api-reading'},
    'sys.patches': {'tier': 'read', 'permission': 'patches.read', 'consent': False, 'evidence': 'api-reading'},
    'net.test': {'tier': 'read', 'permission': 'network.test', 'consent': False, 'evidence': 'phone-side-result'},
    'log.tail': {'tier': 'read', 'permission': 'log.read', 'consent': False, 'evidence': 'agent-log'},
    'export.contacts': {'tier': 'read', 'permission': 'export.contacts', 'consent': True, 'evidence': 'payload-hash'},
    'file.echo-test': {'tier': 'confirmed', 'permission': 'files.test', 'consent': True, 'evidence': 'read-back-hash'},
    'file.send': {'tier': 'confirmed', 'permission': 'files.send', 'consent': True, 'evidence': 'read-back-hash'},
    'install.open': {'tier': 'confirmed', 'permission': 'installer.open', 'consent': True, 'evidence': 'none'},
}
PERMISSIONS = sorted({v['permission'] for v in OPERATIONS.values() if v['permission']})
# Things that are refused whatever a client or an agent says.
FORBIDDEN = ('shell', 'exec', 'system.write', 'jailbreak', 'flash', 'patch.apply', 'file.delete-system')
LEVELS = ('agent-connected', 'operation-completed', 'device-verified')


def canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sign(secret: bytes, body: dict) -> str:
    return hmac.new(secret, canonical(body), hashlib.sha256).hexdigest()


def seal(secret: bytes, body: dict) -> dict:
    return {**body, 'sig': sign(secret, body)}


def open_message(secret: bytes, message: dict) -> dict:
    if not isinstance(message, dict) or len(canonical(message)) > MAX_MESSAGE:
        raise ValueError('Invalid agent message')
    body = {k: v for k, v in message.items() if k != 'sig'}
    if not hmac.compare_digest(str(message.get('sig', '')), sign(secret, body)):
        raise ValueError('Agent message failed authentication')
    if body.get('v') != VERSION:
        raise ValueError('Unsupported agent protocol version')
    return body


def derive_secret(pairing_code: str, host_nonce: str, agent_nonce: str) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', pairing_code.encode(), f'{host_nonce}:{agent_nonce}'.encode(), 20_000)


def new_code() -> str:
    return f'{secrets.randbelow(10**6):06d}'
