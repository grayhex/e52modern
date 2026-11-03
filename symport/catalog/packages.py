"""Shared structural package validation for Catalog and Device Manager."""
from __future__ import annotations

import io
import zipfile
from pathlib import PurePosixPath
from urllib.parse import urlsplit

MAX_PACKAGE = 32 * 1024 * 1024


def attributes(raw: bytes) -> dict[str, str]:
    if len(raw) > 65536:
        raise ValueError('Manifest exceeds 64 KiB')
    try:
        text = raw.decode('utf-8-sig').replace('\r\n', '\n')
    except UnicodeDecodeError as exc:
        raise ValueError('Manifest must be UTF-8') from exc
    lines = []
    for line in text.splitlines():
        if line.startswith(' ') and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    result = {}
    for line in lines:
        if not line:
            break  # Only the main manifest section, never signature sections.
        key, sep, value = line.partition(':')
        if not sep or key in result:
            raise ValueError('Malformed or duplicate manifest attribute')
        result[key] = value.strip()
    return result


def validate_package(name: str, raw: bytes, jar: tuple[str, bytes] | None = None) -> dict:
    if not raw or len(raw) > MAX_PACKAGE:
        raise ValueError('Package must be between 1 byte and 32 MiB')
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in ('.sis', '.sisx'):
        from symport.sis.reader import inspect
        info = inspect(raw)
        if not all(info[k] for k in ('controller_crc_ok', 'data_crc_ok', 'uid_checksum_ok')):
            raise ValueError('SIS checksum validation failed')
        if any(f.get('hash_ok') is False for f in info['files']):
            raise ValueError('SIS payload hash mismatch')
        return {'format': suffix[1:], 'signed': info['signed'],
                'signature_verification': 'not-verified', 'dependencies': info['dependencies']}
    if suffix == '.jar':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                if len(entries) > 10000 or sum(e.file_size for e in entries) > 64 * 1024 * 1024:
                    raise ValueError('JAR expansion limits exceeded')
                names = [e.filename for e in entries]
                if len(names) != len(set(names)) or any('..' in PurePosixPath(n).parts or n.startswith('/') for n in names):
                    raise ValueError('Unsafe or duplicate JAR entries')
                if not any(n.endswith('.class') for n in names):
                    raise ValueError('JAR has no classes')
                if archive.testzip() is not None:
                    raise ValueError('Corrupted JAR entry')
                manifest = attributes(archive.read('META-INF/MANIFEST.MF'))
        except (zipfile.BadZipFile, KeyError, NotImplementedError, RuntimeError) as exc:
            raise ValueError('Invalid JAR archive or missing manifest') from exc
        for key in ('MIDlet-Name', 'MIDlet-Version', 'MIDlet-Vendor', 'MIDlet-1'):
            if not manifest.get(key):
                raise ValueError('JAR missing ' + key)
        return {'format': 'jar', 'manifest': manifest,
                'midp': manifest.get('MicroEdition-Profile', 'unknown'),
                'cldc': manifest.get('MicroEdition-Configuration', 'unknown'),
                'permissions': manifest.get('MIDlet-Permissions', ''),
                'optional_permissions': manifest.get('MIDlet-Permissions-Opt', '')}
    if suffix == '.jad':
        descriptor = attributes(raw)
        for key in ('MIDlet-Name', 'MIDlet-Version', 'MIDlet-Vendor', 'MIDlet-Jar-URL', 'MIDlet-Jar-Size'):
            if not descriptor.get(key):
                raise ValueError('JAD missing ' + key)
        if not jar:
            return {'format': 'jad', 'paired': False, 'descriptor': descriptor}
        jar_name, jar_raw = jar
        url = urlsplit(descriptor['MIDlet-Jar-URL'])
        if PurePosixPath(url.path).name != jar_name or int(descriptor['MIDlet-Jar-Size']) != len(jar_raw):
            raise ValueError('JAD/JAR filename or size mismatch')
        manifest = validate_package(jar_name, jar_raw)['manifest']
        if any(descriptor[k] != manifest[k] for k in ('MIDlet-Name', 'MIDlet-Version', 'MIDlet-Vendor')):
            raise ValueError('JAD/JAR identity mismatch')
        return {'format': 'jad', 'paired': True, 'descriptor': descriptor}
    raise ValueError('Unsupported package format')
