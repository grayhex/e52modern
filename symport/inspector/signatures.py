"""Bounded SIS signature verification. A valid signature does not establish phone trust."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dsa, ec, padding, rsa

from symport.sis import fields as f
from symport.sis.reader import _decompress

ALGORITHMS = {'1.2.840.113549.1.1.5': hashes.SHA1, '1.2.840.113549.1.1.11': hashes.SHA256,
              '1.2.840.10040.4.3': hashes.SHA1}


def certificates(raw):
    if len(raw) > 512 * 1024:
        raise ValueError('Certificate chain exceeds limit')
    result = []
    while raw:
        if len(result) >= 16 or len(raw) < 2 or raw[0] != 0x30:
            raise ValueError('Invalid DER certificate chain')
        size, offset = raw[1], 2
        if size & 0x80:
            count = size & 0x7f
            if not 1 <= count <= 4 or len(raw) < 2 + count:
                raise ValueError('Invalid DER length')
            size, offset = int.from_bytes(raw[2:2+count], 'big'), 2 + count
        end = offset + size
        if end > len(raw):
            raise ValueError('Truncated DER certificate')
        result.append(x509.load_der_x509_certificate(raw[:end]))
        raw = raw[end:]
    return result


def verify(public, signature, data, algorithm):
    if isinstance(public, rsa.RSAPublicKey):
        public.verify(signature, data, padding.PKCS1v15(), algorithm)
    elif isinstance(public, dsa.DSAPublicKey):
        public.verify(signature, data, algorithm)
    elif isinstance(public, ec.EllipticCurvePublicKey):
        public.verify(signature, data, ec.ECDSA(algorithm))
    else:
        raise UnsupportedAlgorithm('Unsupported public key')


def metadata(cert, at):
    start, end = cert.not_valid_before_utc, cert.not_valid_after_utc
    return {'subject': cert.subject.rfc4514_string(), 'issuer': cert.issuer.rfc4514_string(),
            'serial': hex(cert.serial_number), 'sha256': cert.fingerprint(hashes.SHA256()).hex(),
            'not_before': start.isoformat(), 'not_after': end.isoformat(),
            'validity': 'not-yet-valid' if at < start else 'expired' if at > end else 'valid',
            'key_type': type(cert.public_key()).__name__, 'self_issued': cert.subject == cert.issuer,
            'extensions': [{'oid': e.oid.dotted_string, 'critical': e.critical,
                            'interpreted': not isinstance(e.value, x509.UnrecognizedExtension)} for e in cert.extensions]}


def controller(raw):
    cursor = f.Cursor(raw, 16)
    _, contents, _ = cursor.field(f.T_CONTENTS)
    cursor = f.Cursor(contents)
    if cursor.peek_type() == f.T_CONTROLLER_CHECKSUM:
        cursor.field(f.T_CONTROLLER_CHECKSUM)
    if cursor.peek_type() == f.T_DATA_CHECKSUM:
        cursor.field(f.T_DATA_CHECKSUM)
    _, compressed, _ = cursor.field(f.T_COMPRESSED)
    _, body, _ = f.Cursor(_decompress(compressed)).field(f.T_CONTROLLER)
    return body


def inspect_signatures(raw, at=None):
    at = at or datetime.now(UTC)
    body, result, dependencies = controller(raw), [], []
    cursor = f.Cursor(body)
    while not cursor.done():
        start = cursor.pos
        kind, payload, _ = cursor.field()
        if kind == f.T_PREREQUISITES:
            dep = f.Cursor(payload)
            array_index = 0
            while not dep.done():
                _, entries = dep.array(f.T_DEPENDENCY)
                for entry in entries:
                    item, dc = {'kind': 'target-device' if array_index == 0 else 'dependency'}, f.Cursor(entry)
                    while not dc.done():
                        t, p, _ = dc.field()
                        if t == f.T_UID:
                            item['uid'] = f'0x{int.from_bytes(p, "little"):08x}'
                        elif t == 5:  # SISVersionRange
                            versions = f.Cursor(p)
                            item['versions'] = []
                            import struct
                            while not versions.done():
                                _, v, _ = versions.field(f.T_VERSION)
                                item['versions'].append(list(struct.unpack('<3i', v)))
                    dependencies.append(item)
                array_index += 1
        if kind != f.T_SIGNATURE_CHAIN:
            continue
        if len(result) >= 16:
            raise ValueError('Too many SIS signature chains')
        entry = {'status': 'invalid', 'certificates': [], 'signatures': [], 'phone_trust': 'unknown'}
        try:
            sc = f.Cursor(payload)
            _, signatures = sc.array(f.T_SIGNATURE)
            _, cp, _ = sc.field(f.T_CERTIFICATE_CHAIN)
            _, der, _ = f.Cursor(cp).field(f.T_BLOB)
            chain = certificates(der)
            if not chain or not signatures or len(signatures) > 16:
                raise ValueError('Missing certificate/signature')
            entry['certificates'] = [metadata(c, at) for c in chain]
            for signature in signatures:
                fields = f.Cursor(signature)
                _, algorithm, _ = fields.field(f.T_SIGNATURE_ALGORITHM)
                _, oid, _ = f.Cursor(algorithm).field(f.T_STRING)
                oid = oid.decode('utf-16-le')
                _, value, _ = fields.field(f.T_BLOB)
                status = 'unsupported'
                if oid in ALGORITHMS:
                    try:
                        verify(chain[0].public_key(), value, body[:start], ALGORITHMS[oid]())
                        status = 'valid'
                    except InvalidSignature:
                        status = 'invalid'
                entry['signatures'].append({'oid': oid, 'status': status, 'legacy_sha1': oid.endswith('.5') or oid == '1.2.840.10040.4.3',
                                            'signed_bytes': start, 'signed_sha256': hashlib.sha256(body[:start]).hexdigest()})
            entry['chain_links'] = []
            for child, issuer in zip(chain, chain[1:], strict=False):
                status = 'invalid'
                if child.issuer == issuer.subject:
                    try:
                        verify(issuer.public_key(), child.signature, child.tbs_certificate_bytes, child.signature_hash_algorithm)
                        status = 'valid'
                    except InvalidSignature:
                        pass
                entry['chain_links'].append(status)
            statuses = [s['status'] for s in entry['signatures']] + entry['chain_links']
            entry['status'] = 'invalid' if 'invalid' in statuses else 'unsupported' if 'unsupported' in statuses else 'valid'
        except (ValueError, UnsupportedAlgorithm) as exc:
            entry['error'] = str(exc)[:200]
        result.append(entry)
    return {'chains': result, 'dependencies': dependencies, 'at': at.isoformat(),
            'status': 'unsigned' if not result else 'invalid' if any(c['status'] == 'invalid' for c in result) else 'unsupported' if any(c['status'] == 'unsupported' for c in result) else 'valid',
            'trust': 'unknown', 'revocation': 'not-checked', 'phone_constraints': 'not-verified'}
