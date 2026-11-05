"""CFW Security Scanner (#46): read-only pattern audit of a firmware tree against a versioned advisory database.

It never runs, installs or exploits anything and never uploads a file anywhere. It looks for known
risky *patterns* (a string in a binary, a path convention) and compares a version *you declare* with
an advisory's affected list. The report vocabulary is ``vulnerable-version``, ``suspicious-pattern``,
``no-pattern-found``, ``unknown`` and ``not-tested``; ``no-pattern-found`` is never proof of safety.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

DB = Path(__file__).with_name('advisories.json')
MAX_FILE = 32 * 1024 * 1024
MAX_FILES = 20_000
MAX_BYTES = 512 * 1024 * 1024
DEADLINE = 120.0
VERDICTS = ('vulnerable-version', 'suspicious-pattern', 'no-pattern-found', 'unknown', 'not-tested')
SCANNABLE = ('e32-exe', 'e32-dll', 'rom-image-exe', 'rom-image-dll', 'plugin', 'data', 'other', 'text', 'resource')


def load_db() -> dict:
    document = json.loads(DB.read_text(encoding='utf-8'))
    if document.get('schema') != 1:
        raise ValueError('Unsupported advisory database')
    rule_ids = {r['id'] for r in document['rules']}
    for a in document['advisories']:
        if any(r not in rule_ids for r in a['rules']):
            raise ValueError('Advisory refers to an unknown rule: ' + a['id'])
    for r in document['rules']:
        if r.get('regex'):
            re.compile(r['regex'])
    return document


def _version_key(text: str) -> str:
    return re.sub(r'[^a-z0-9.]+', '', str(text).lower().replace('delight', '').replace('v', ''))


def declared_match(advisory: dict, declared: dict) -> dict | None:
    """Match a *user-declared* CFW/model/version against the affected list (never read from the image)."""
    if not declared or str(declared.get('cfw', '')).lower() != advisory['cfw']:
        return None
    model = re.sub(r'\s+', ' ', str(declared.get('model', '')).lower().replace('nokia ', '')).strip()
    for item in advisory['affected']:
        if model and re.sub(r'\s+', ' ', item['model'].lower().replace('nokia ', '')).strip() == model \
                and _version_key(declared.get('version', '')) == _version_key(item['version']):
            return item
    return None


def _find(rule: dict, blob: bytes):
    if rule.get('strings'):
        for text in rule['strings']:
            for encoded in (text.encode('ascii'), text.encode('utf-16-le')):
                at = blob.find(encoded)
                if at >= 0:
                    yield at, text
                    break
    if rule.get('regex'):
        pattern = re.compile(rule['regex'])
        for encoding in ('latin-1', 'utf-16-le'):
            text = blob.decode(encoding, errors='ignore')
            found = pattern.search(text)
            if found:
                yield found.start() * (2 if encoding == 'utf-16-le' else 1), found.group(0)[:80]
                break


def scan(entries: list[dict], read, declared: dict | None = None, deadline: float = DEADLINE) -> dict:
    """``entries``: index entries (path, kind, size, sha256, e32); ``read(entry)`` returns the file bytes."""
    db = load_db()
    started = time.monotonic()
    findings, not_tested, scanned, total = [], [], 0, 0
    if not entries:
        return report(db, 'unknown', findings, not_tested, scanned, 'The image contains no readable files.', declared, [])
    for entry in entries[:MAX_FILES]:
        if entry['kind'] not in SCANNABLE:
            continue
        if time.monotonic() - started > deadline:
            not_tested.append({'path': entry['path'], 'reason': 'time limit reached'})
            continue
        e32 = entry.get('e32') or {}
        if e32.get('compression') not in (None, 'none', 0):
            not_tested.append({'path': entry['path'], 'reason': 'compressed E32 image: its code cannot be searched'})
            continue
        if entry['size'] > MAX_FILE or total + entry['size'] > MAX_BYTES:
            not_tested.append({'path': entry['path'], 'reason': 'larger than the scan limits'})
            continue
        try:
            blob = read(entry)
        except (ValueError, OSError) as exc:
            not_tested.append({'path': entry['path'], 'reason': 'unreadable: ' + str(exc)[:80]})
            continue
        scanned += 1
        total += len(blob)
        digest = hashlib.sha256(blob).hexdigest()
        for rule in db['rules']:
            for offset, matched in _find(rule, blob):
                findings.append({'rule': rule['id'], 'title': rule['title'], 'status': rule['status_on_match'], 'advisory': rule['advisory'],
                                 'path': entry['path'], 'sha256': digest, 'offset': offset, 'matched': matched, 'reliability': rule['reliability']})
    if len(entries) > MAX_FILES:
        not_tested.append({'path': '(remaining files)', 'reason': f'only the first {MAX_FILES} files were scanned'})
    versions = []
    for a in db['advisories']:
        hit = declared_match(a, declared or {})
        if hit:
            versions.append({'advisory': a['id'], 'status': 'vulnerable-version', 'basis': 'declared by you; not verified from the image', 'matched': hit})
    suspicious = [f for f in findings if f['status'] == 'suspicious-pattern']
    if versions:
        verdict = 'vulnerable-version'
    elif suspicious:
        verdict = 'suspicious-pattern'
    elif scanned == 0:
        verdict = 'unknown'
    else:
        verdict = 'no-pattern-found'
    return report(db, verdict, findings, not_tested, scanned, None, declared, versions)


def report(db, verdict, findings, not_tested, scanned, reason, declared, versions) -> dict:
    return {'schema': 'symport.cfw-scan/1', 'db_version': db['db_version'], 'verdict': verdict, 'findings': findings[:500], 'findings_total': len(findings),
            'declared_versions': versions, 'declared': declared or None,
            'coverage': {'files_scanned': scanned, 'not_tested': not_tested[:200], 'not_tested_total': len(not_tested)},
            'proof_of_safety': False, 'reason': reason,
            'statement': 'A pattern match is a lead, not a verdict on behaviour. No match is not proof of safety. Nothing was run, installed or exploited, and no file left this server.',
            'advisories': {a['id']: {k: a[k] for k in ('title', 'published', 'severity', 'cwe', 'sources', 'platform', 'caveats')} for a in db['advisories']
                           if any(f['advisory'] == a['id'] for f in findings) or any(v['advisory'] == a['id'] for v in versions)}}
