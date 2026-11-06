"""CFW Research (#42): author-published sources, a structured inventory of potential system modifications.

Metadata comes only from the sources' own pages (``cfw_sources.json``). The inventory lists *leads*
found by file name and file content in an image the user supplied (and, with a baseline image, whether
a file is new or changed relative to it). Missing data is ``unknown``; nothing is declared working.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SOURCES = Path(__file__).with_name('cfw_sources.json')
MAX_TEXT = 256 * 1024
MAX_URLS = 200
TEXT_KINDS = ('text', 'data', 'other', 'resource')
URL = re.compile(rb'https?://[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]{4,200}')
NAME_RULES = {
    'ssl-ca': re.compile(r'cacert|ca-?cert|certstore|\.cer$|\.der$|\bssl\b|mozilla', re.I),
    'uaprof': re.compile(r'uaprof|\.rdf$', re.I),
    'autostart': re.compile(r'domainsrv|startup|autostart|rompatcher|10202be9|private/101f875a', re.I),
    'connectivity': re.compile(r'conntest|connectivity', re.I),
}
REPLACED = ('e32-exe', 'e32-dll', 'sis', 'plugin')


def load_sources() -> dict:
    document = json.loads(SOURCES.read_text(encoding='utf-8'))
    if document.get('schema') != 1:
        raise ValueError('Unsupported CFW sources')
    return document


def inventory(entries: list[dict], read, baseline: list[dict] | None = None) -> dict:
    base = {e['path'].lower(): e for e in (baseline or [])}
    urls: dict[str, dict] = {}
    leads: dict[str, list] = {k: [] for k in NAME_RULES}
    uaprof_content, replaced = [], []
    for e in entries:
        for cat, pattern in NAME_RULES.items():
            if pattern.search(e['path']) and len(leads[cat]) < 200:
                leads[cat].append({'path': e['path'], 'sha256': e.get('sha256'), 'basis': 'file-name'})
        if e['kind'] in TEXT_KINDS and 0 < e['size'] <= MAX_TEXT and len(urls) < MAX_URLS:
            try:
                blob = read(e)
            except (ValueError, OSError):
                continue
            for text in (blob, blob.decode('utf-16-le', errors='ignore').encode('latin-1', errors='ignore')):
                for found in URL.findall(text):
                    urls.setdefault(found.decode('latin-1'), {'url': found.decode('latin-1'), 'path': e['path'], 'sha256': e.get('sha256')})
            if b'UAProf' in blob or b'uaprof' in blob.lower():
                uaprof_content.append({'path': e['path'], 'sha256': e.get('sha256'), 'basis': 'file-content'})
        if e['kind'] in REPLACED:
            old = base.get(e['path'].lower()) if baseline is not None else None
            state = ('new-relative-to-baseline' if old is None else 'changed-relative-to-baseline' if old.get('sha256') != e.get('sha256') else 'identical-to-baseline') if baseline is not None else 'present-origin-unknown'
            if state != 'identical-to-baseline' and len(replaced) < 500:
                replaced.append({'path': e['path'], 'kind': e['kind'], 'sha256': e.get('sha256'), 'origin': state})
    leads['uaprof'].extend(uaprof_content)
    return {'categories': {
                'urls': {'items': list(urls.values()), 'basis': 'text found in readable files; a URL here is not shown to be used'},
                **{k: {'items': v, 'basis': 'file name and content leads; behaviour is not established'} for k, v in leads.items()},
                'replaced-binaries': {'items': replaced, 'basis': 'relative to the baseline image' if baseline is not None else 'no baseline supplied: origin unknown'}},
            'baseline': baseline is not None,
            'statement': 'Leads for review only. Absent data is unknown; nothing is declared working, safe or applied to a phone.'}
