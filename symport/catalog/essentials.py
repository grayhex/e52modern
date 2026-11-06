"""Verified Essentials (#40): per-model profiles built on the existing catalog and collections.

A profile is a list of catalog cards. For a chosen phone model each card is either *eligible* (a
pinned, validated distribution exists and the catalog finds no problem for that model) or
*excluded* with the reasons. Eligibility is static compatibility: it never claims hardware
verification or installation, and manual-only or unavailable applications are never transferred.
"""
from __future__ import annotations

import json
from pathlib import Path

from symport.phone.registry import selectable_profiles

STATUS_BLOCK = ('unsupported', 'unavailable')


class Essentials:
    def __init__(self, service):
        self.service = service
        catalog_dir = Path(service.catalog.directory) if hasattr(service.catalog, 'directory') else None
        path = (catalog_dir or Path(__file__).resolve().parents[2] / 'catalog') / 'essentials.json'
        if not path.exists():
            path = Path(__file__).resolve().parents[2] / 'catalog' / 'essentials.json'
        self.data = json.loads(path.read_text(encoding='utf-8'))
        if self.data.get('schema') != 1:
            raise ValueError('Unsupported essentials data')

    def profiles(self) -> list[dict]:
        return [{'id': p['id'], 'title': p['title'], 'models': p['models'], 'apps': p['apps']} for p in self.data['profiles']]

    def item(self, app_id: str, model: str) -> dict:
        catalog = self.service.catalog
        entry = catalog.entries.get(app_id)
        if not entry:
            return {'id': app_id, 'eligible': False, 'reasons': ['unknown-application'], 'name': app_id}
        arts = catalog.sources.get(entry['source_id'], {}).get('artifacts', [])
        reasons, comp = [], {}
        try:
            plan = catalog.plan([app_id], model)
            reasons += plan['problems']
            comp = plan['model_compatibility'].get(app_id, {})
        except ValueError as exc:
            reasons.append(str(exc)[:200])
        if entry.get('delivery') != 'automatic' or not arts:
            reasons.append('manual-only: no pinned distribution (use the author link)')
        if comp.get('status') in STATUS_BLOCK:
            reasons.append(f"model-{comp['status']}: {comp.get('reason', '')}")
        network = entry.get('network', 'unknown')
        return {
            'id': app_id, 'name': entry['name'], 'category': entry['category'], 'version': entry['version'],
            'licence': entry.get('license'), 'author': entry.get('homepage'), 'platforms': entry['platforms'],
            'eligible': not reasons, 'reasons': reasons,
            'evidence': {'declared': entry['compatibility'], 'model': comp.get('status', 'not-tested'),
                         'hardware': 'verified-on-model' if comp.get('status') == 'verified' else 'not-tested',
                         'installation': comp.get('installation', 'not-tested'), 'basis': comp.get('basis'),
                         'pinned_sha256': [a['sha256'] for a in arts]},
            'size': sum(a['size'] for a in arts), 'format': entry.get('format'),
            'network': network, 'needs_companion_server': network not in ('offline', 'unknown') and 'server' in (entry.get('backend') or '').lower(),
            'tls_note': entry.get('tls'), 'guide': (entry.get('guide') or {}).get('title'),
        }

    def evaluate(self, profile_id: str, model: str) -> dict:
        profile = next((p for p in self.data['profiles'] if p['id'] == profile_id), None)
        if profile is None:
            raise ValueError('Unknown essentials profile')
        if model not in selectable_profiles():
            raise ValueError('Choose a supported phone model')
        base = {'profile': profile_id, 'title': profile['title'], 'model': model, 'guide': self.data['guide_2026'],
                'statement': 'Static compatibility only: nothing here proves installation or hardware operation. '
                             'The recovery transfer copies files; you install them on the phone.'}
        if model not in profile['models']:
            return {**base, 'applicable': False, 'items': [], 'eligible_ids': [], 'order': [], 'bytes': 0,
                    'reason': 'This profile does not target the selected model.'}
        items = [self.item(a, model) for a in profile['apps']]
        eligible = [i['id'] for i in items if i['eligible']]
        order, extra, size = [], [], 0
        if eligible:
            plan = self.service.catalog.plan(eligible, model)
            order, extra, size = plan['ids'], plan['added_dependencies'], plan['bytes']
        return {**base, 'applicable': True, 'items': items, 'eligible_ids': eligible, 'order': order,
                'added_dependencies': extra, 'bytes': size,
                'install_order_note': 'Copy in this order and install in this order on the phone; shared UIDs and versions are checked by the catalog plan.'}

    def to_collection(self, profile_id: str, model: str) -> dict:
        result = self.evaluate(profile_id, model)
        if not result['applicable'] or not result['eligible_ids']:
            raise ValueError('Nothing eligible to save for this model')
        title = result['title']['en']
        return self.service.collections.execute({'action': 'collection-save', 'name': f'{title} · {model}'[:60],
                                                 'profile': model, 'ids': result['eligible_ids']})
