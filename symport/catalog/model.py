"""Curated metadata and dependency planning; never accept client download URLs."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from symport.phone.registry import selectable_profiles

from .compatibility import assessment, evidence, platform_evidence

STATUSES = {'verified-on-e52', 'verified-on-s60', 'likely-compatible', 'untested', 'unsupported', 'unavailable'}
CATEGORIES = {'maps', 'communication', 'internet', 'system', 'documents', 'multimedia', 'games', 'development', 'high-risk'}
ID = re.compile(r'^[a-z][a-z0-9-]{1,63}$')


def validate_entry(entry: dict) -> None:
    required = {'id', 'name', 'category', 'developer', 'description', 'version', 'release_date',
                'platforms', 'format', 'homepage', 'license', 'redistribution', 'dependencies',
                'network', 'backend', 'tls', 'signature', 'compatibility', 'e52_evidence',
                'sources', 'checked_at', 'source_id', 'limitations', 'collection', 'delivery', 'manual_url', 'delivery_reason'}
    if not isinstance(entry, dict) or not required <= entry.keys():
        raise ValueError('Catalog entry missing required fields')
    for key in ('id', 'name', 'developer', 'description', 'version', 'homepage', 'license', 'redistribution', 'backend', 'tls', 'signature', 'checked_at'):
        if not isinstance(entry[key], str) or not entry[key]:
            raise ValueError('Catalog text required: ' + key)
    if not ID.fullmatch(entry['id']) or entry['category'] not in CATEGORIES or entry['compatibility'] not in STATUSES:
        raise ValueError('Invalid catalog identifier, category or compatibility')
    if entry['delivery'] not in ('automatic', 'manual'):
        raise ValueError('Invalid delivery mode')
    if entry['format'] not in ('sis', 'sisx', 'jar', 'jar+jad') or entry['network'] not in ('offline', 'online', 'mixed'):
        raise ValueError('Invalid platform/format metadata')
    for key in ('dependencies', 'platforms', 'sources', 'limitations', 'collection'):
        if not isinstance(entry[key], list):
            raise ValueError('Catalog list required: ' + key)
    if entry['compatibility'] == 'verified-on-e52' and not entry['e52_evidence']:
        raise ValueError('E52 verification requires evidence')
    if entry.get('minimum_symbian') is not None and not re.fullmatch(r'9\.[1-4]|\^3|Anna|Belle(?: Refresh)?', str(entry['minimum_symbian'])):
        raise ValueError('Invalid minimum Symbian version')
    if not isinstance(entry.get('model_evidence', {}), dict):
        raise ValueError('Model evidence must be a mapping')
    for key, report in entry.get('model_evidence', {}).items():
        if key not in selectable_profiles() or not isinstance(report, dict) or report.get('status') not in ('verified', 'not-tested', 'unsupported'):
            raise ValueError('Invalid per-model compatibility evidence')
        if report['status'] == 'verified' and (not report.get('sources') or not report.get('package_sha256') or not re.fullmatch(r'[a-f0-9]{64}', report['package_sha256'])):
            raise ValueError('Model verification requires sources and exact package SHA-256')
    date.fromisoformat(entry['checked_at'])
    if entry['release_date'] is not None:
        date.fromisoformat(entry['release_date'])
    for url in [entry['homepage'], entry['manual_url'], *entry['sources']]:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Catalog links must be credential-free HTTPS')
    if not entry['sources'] or not entry['checked_at']:
        raise ValueError('Catalog sources and research date required')


class Catalog:
    def __init__(self, root: Path):
        self.entries = {}
        for path in sorted((root / 'apps').glob('*.json')):
            entry = json.loads(path.read_text(encoding="utf-8"))
            validate_entry(entry)
            if entry['id'] in self.entries:
                raise ValueError('Duplicate catalog ID')
            entry['model_compatibility'] = evidence(entry)
            entry['platform_compatibility'] = platform_evidence(entry)
            self.entries[entry['id']] = entry
        self.sources = json.loads((root / 'sources.json').read_text(encoding="utf-8"))
        self.research = json.loads((root / 'research.json').read_text(encoding="utf-8"))
        for entry in self.entries.values():
            if entry['source_id'] and entry['source_id'] not in self.sources:
                raise ValueError('Unknown curated source: ' + entry['source_id'])
            pins = {a['sha256'] for a in self.sources.get(entry['source_id'], {}).get('artifacts', [])}
            for report in entry.get('model_evidence', {}).values():
                if report['status'] == 'verified' and pins and report['package_sha256'] not in pins:
                    raise ValueError('Model test SHA-256 differs from the current distribution')
            for other in entry.get('conflicts_with', []):
                if other not in self.entries:
                    raise ValueError('Unknown conflicting application: ' + str(other))

    def list(self, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        if not isinstance(filters, dict):
            raise ValueError('Catalog filters must be an object')
        query = str(filters.get('query', '')).casefold()
        return [entry for entry in self.entries.values()
                if (entry['category'] != 'high-risk' or filters.get('category') == 'high-risk')
                and query in (entry['name'] + ' ' + entry['description']).casefold()
                and all(not filters.get(k) or entry[k] == filters[k] for k in ('category', 'network', 'compatibility'))
                and (not filters.get('format') or entry['format'].startswith(filters['format']))
                and (not filters.get('delivery') or entry['delivery'] == filters['delivery'])
                and (not filters.get('collection') or filters['collection'] in entry['collection'])]

    def plan(self, selected: list[str], device: str = 'nokia-e52') -> dict:
        if device not in selectable_profiles():
            raise ValueError('Choose a supported Nokia compatibility profile')
        if not isinstance(selected, list) or not 0 < len(selected) <= 50 or any(not isinstance(i, str) for i in selected):
            raise ValueError('Select 1–50 applications')
        ordered, visiting, done, problems = [], set(), set(), []
        def visit(key):
            if key in visiting:
                raise ValueError('Dependency cycle: ' + key)
            if key in done:
                return
            entry = self.entries.get(key)
            if not entry:
                problems.append('Missing dependency/application: ' + str(key))
                return
            visiting.add(key)
            if assessment(entry, device)['status'] == 'unsupported':
                problems.append(entry['name'] + ': selected model is outside the declared target profiles')
            if entry['delivery'] == 'manual':
                problems.append(entry['name'] + ': manual download only; use the author link and normal package transfer')
            elif entry['compatibility'] in ('unsupported', 'unavailable') or not entry['source_id']:
                problems.append(entry['name'] + ': no approved compatible distribution')
            if entry['category'] == 'high-risk':
                problems.append(entry['name'] + ': high-risk software excluded from batch operations')
            for dependency in entry['dependencies']:
                visit(dependency)
            visiting.remove(key)
            done.add(key)
            ordered.append(key)
        for key in selected:
            visit(key)
        for key in ordered:
            for other in self.entries[key].get('conflicts_with', []):
                if other in ordered:
                    problems.append(self.entries[key]['name'] + ' conflicts with ' + self.entries[other]['name']
                                    + ': they share one application identity; choose one')
        filenames = {}
        for key in ordered:
            for artifact in self.sources.get(self.entries[key]['source_id'], {}).get('artifacts', []):
                previous = filenames.get(artifact['name'])
                if previous and previous != artifact['sha256']:
                    problems.append('Conflicting package filename: ' + artifact['name'] + '; transfer in separate batches/folders')
                filenames[artifact['name']] = artifact['sha256']
        size = sum(sum(a['size'] for a in self.sources[self.entries[key]['source_id']]['artifacts'])
                   for key in ordered if self.entries[key]['source_id'] in self.sources)
        return {'ids': ordered, 'added_dependencies': [key for key in ordered if key not in selected],
                'bytes': size, 'problems': problems, 'device': device,
                'requirements': {key: self.entries[key].get('requirements', []) for key in ordered},
                'runtime_requirements': {key: self.entries[key]['runtime_requirements'] for key in ordered
                                         if self.entries[key].get('runtime_requirements')},
                'model_compatibility': {key: assessment(self.entries[key], device) for key in ordered},
                'warning': 'Package validation does not establish hardware compatibility or installation.'}
