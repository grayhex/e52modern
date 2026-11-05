"""SymPort Revive: inspect → plan → prepare → verify, always through ``DeviceManager``.

Nothing here opens a transport of its own. Facts carry their source (observed / documented /
manual); manual input is stored and shown separately and never overrides a device report.
Files copied to the phone are *transferred*, never *installed*.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path

from symport.catalog.service import now, save
from symport.phone.models import documented_model

from . import checks as C
from .profiles import (
    MANUAL_OPERATIONS,
    MANUAL_RESULTS,
    OPERATIONS,
    PLANNING_MARGIN,
    PROFILES,
    RIGHTS_SCOPES,
)

SCHEMA = 'symport.revive/1'
SAFETY_ACTIONS = ('safety-state', 'safety-plan', 'safety-snapshot', 'safety-apply', 'safety-rollback',
                  'safety-postflight', 'safety-checklist', 'safety-export', 'safety-ack', 'safety-view')
CONTROL = re.compile(r'[\x00-\x1f\x7f]')
SAFE_ID = re.compile(r'^[0-9a-f]{16,64}$')


def _text(value, limit=120):
    return CONTROL.sub(' ', value).strip()[:limit] if isinstance(value, str) else ''


def manual_input(raw) -> dict:
    """Typed-in identity. Kept apart from device reads and never trusted over them."""
    raw = raw if isinstance(raw, dict) else {}
    return {k: _text(raw.get(k)) for k in ('model', 'rm', 'firmware')}


class ReviveService:
    def __init__(self, repo: Path, devices):
        self.devices = devices
        self.root = repo / 'build' / 'symport' / 'revive'
        self.lock = threading.RLock()
        # Later stages plug in here (restore points, kit catalogues); absent means "not available".
        self.extensions: dict[str, object] = {}
        from .safety import SafetyNet
        from .tls import TlsRevival
        self.tls = TlsRevival(self)
        self.safety = SafetyNet(self)
        # Scenario name -> builder(row, facts, request) -> saved plan; registered by each wizard.
        self.scenarios: dict = {}
        self.tls.register_safety()
        from .reborn import RebornWizard
        self.reborn = RebornWizard(self)
        from .services import LegacyServices
        self.services = LegacyServices(self)
        from symport.agent import AgentHost
        self.agent = AgentHost(None, journal=self.devices.record)
        from .addons import AddonManager
        self.addons = AddonManager(self)

    # ---- storage ---------------------------------------------------------------------------
    def _key(self, row: dict) -> str:
        basis = '\x1f'.join(str(row.get(k) or '') for k in ('capability_fingerprint', 'connection_identity', 'id'))
        return hashlib.sha256(basis.encode()).hexdigest()[:32]

    def _load(self, kind: str, key: str) -> dict:
        path = self.root / kind / (key + '.json')
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _save(self, kind: str, key: str, value: dict) -> None:
        save(self.root / kind / (key + '.json'), value)

    # ---- device access -----------------------------------------------------------------------
    def _rows(self) -> list[dict]:
        return self.devices.execute({'action': 'discover'})['devices']

    def _row(self, device) -> tuple[dict | None, list[dict]]:
        rows = self._rows()
        if not isinstance(device, str) or not device:
            return None, rows
        return next((d for d in rows if d['id'] == device), None), rows

    def facts(self, row: dict | None, manual: dict) -> dict:
        row = row or {}
        observed = {k: row.get(k) for k in ('model', 'rm', 'product_code', 'firmware', 'transport',
                                            'connection_kind', 'free', 'total', 'storage_scope')}
        observed = {k: (v if v not in ('', None) else None) for k, v in observed.items()}
        caps = row.get('capability_matrix') or {}
        key = self._key(row) if row else ''
        saved = self._load('observations', key) if key else {}
        identity = C.resolve_identity(observed, manual)
        documented = None
        if not identity['profile']:
            documented = documented_model(str(observed.get('model') or manual.get('model') or ''))
        return {'row': row, 'key': key, 'observed': observed, 'manual': manual, 'identity': identity,
                'capabilities': caps, 'documented_family': documented,
                'rights': saved.get('rights'), 'variant_confirmed': bool(saved.get('variant_confirmed')),
                'results': saved.get('results', {}), 'baseline': self._load('baselines', key) if key else {}}

    @staticmethod
    def present(facts: dict) -> dict:
        """Facts for display: each value tagged with its source, manual input kept separate."""
        obs, ident = facts['observed'], facts['identity']
        prof = ident['profile']

        def fact(value, source, note=None):
            return {'value': value, 'source': source if value is not None else 'unknown', 'note': note}

        caps = facts['capabilities']
        verified = sorted(op for op, s in caps.items() if s.get('status') == 'available')
        return {
            'model': fact(obs['model'], 'observed'),
            'rm': fact(obs['rm'], 'observed'),
            'product_code': fact(obs['product_code'], 'observed'),
            'firmware': fact(obs['firmware'], 'observed'),
            'platform': fact(f"S60 {prof['s60']} / Symbian {prof.get('symbian')}" if prof else None, 'documented',
                             'Model profile, not a measured firmware version'),
            'profile': fact(prof['id'] if prof else None, 'documented'),
            'connection': fact(f"{obs['transport']} / {obs['connection_kind']}" if obs['transport'] else None, 'observed'),
            'free': fact(obs['free'], 'observed', obs['storage_scope']),
            'total': fact(obs['total'], 'observed'),
            'capabilities': fact(verified, 'observed', f"{len(caps)} operations in the matrix"),
            'rights': fact(facts['rights']['scope'] if facts['rights'] else None, 'manual',
                           'Your observation; not readable through a file transport'),
            'patches': fact(facts['rights'].get('patches') if facts['rights'] else None, 'manual'),
        }

    # ---- actions -----------------------------------------------------------------------------
    def execute(self, data: dict) -> dict:
        action = data.get('action')
        with self.lock:
            handler = {
                'state': self._state, 'inspect': self._inspect, 'plan': self._plan,
                'observe': self._observe, 'record': self._record, 'baseline': self._baseline,
                'verify': self._verify,
                'home': self._home,
                'tls-state': lambda d: self.tls.state(d), 'tls-fetch': lambda d: self.tls.fetch(d),
                'tls-import': lambda d: self.tls.import_file(d), 'tls-diagnose': lambda d: self.tls.diagnose(d),
                'tls-kit': lambda d: self.tls.kit(d),
                'tls-record': lambda d: self.tls.record(d),
                'reborn-state': lambda d: self.reborn.state(d), 'reborn-import': lambda d: self.reborn.import_file(d),
                'reborn-pin': lambda d: self.reborn.pin(d), 'reborn-backup': lambda d: self.reborn.attest(d),
                'reborn-stage': lambda d: self.reborn.stage(d),
                'services-state': lambda d: self.services.state(d), 'services-diagnose': lambda d: self.services.diagnose(d),
                'services-record': lambda d: self.services.record(d),
                'agent-state': lambda d: self.agent.state(), 'agent-pair-start': lambda d: self.agent.pair_start(),
                'agent-pair-finish': lambda d: self.agent.pair_finish(), 'agent-disconnect': lambda d: self.agent.disconnect(),
                'agent-grant': lambda d: self.agent.grant(d.get('permission'), d.get('seconds', 3600)),
                'agent-revoke': lambda d: self.agent.revoke(d.get('permission')),
                'agent-call': lambda d: self.agent.call(d.get('op'), d.get('args'), d.get('confirm') is True),
                'addons-state': lambda d: self.addons.state(d), 'addons-plan': lambda d: self.addons.plan(d),
                'addons-prepare': lambda d: self.addons.prepare(d), 'addons-open-category': lambda d: self.addons.open_category(d),
                'addons-mark': lambda d: self.addons.mark(d), 'addons-verify-file': lambda d: self.addons.verify_file(d),
                'patch-save': lambda d: self.addons.patch_save(d), 'patch-delete': lambda d: self.addons.patch_delete(d),
            }.get(action)
            if handler is None and isinstance(action, str) and action.startswith('safety-'):
                handler = (lambda d, a=action: self.safety.execute(a, d)) if action in SAFETY_ACTIONS else None
            if handler is None:
                raise ValueError('Unknown Revive operation')
            result = handler(data)
        self.devices.record('revive-' + str(action), 'success')
        return result

    def _state(self, data):
        return {'schema': SCHEMA, 'profiles': {k: self._profile_view(k) for k in PROFILES},
                'planning_margin': PLANNING_MARGIN, 'rights_scopes': list(RIGHTS_SCOPES),
                'extensions': sorted(self.extensions)}

    @staticmethod
    def _profile_view(pid):
        p = PROFILES[pid]
        return {'id': pid, 'title': p['title'], 'summary': p['summary'], 'targets': list(p['targets']),
                'operations': list(p['operations'])}

    def _context(self, data, profile_id=None):
        row, rows = self._row(data.get('device'))
        manual = manual_input(data.get('manual'))
        facts = self.facts(row, manual)
        return row, rows, facts

    def _inspect(self, data):
        row, rows, facts = self._context(data)
        ident = facts['identity']
        evaluated = C.evaluate(facts, 'network-certs')
        reason = None
        if not rows:
            reason = 'no-connection'
        elif row is None:
            reason = 'device-not-selected' if not data.get('device') else 'unknown-device'
        return {'schema': SCHEMA, 'device': (row or {}).get('id'), 'devices': [self._summary(d) for d in rows],
                'reason': reason, 'connected': bool((row or {}).get('connected')),
                'facts': self.present(facts), 'manual': facts['manual'],
                'conflict': ident['conflict'], 'checks': list(evaluated.values()),
                'baseline': facts['baseline'].get('at'),
                'notes': ['Manual input is shown separately and never replaces a device report.']}

    @staticmethod
    def _summary(d):
        return {'id': d['id'], 'name': d.get('name'), 'model': d.get('model'), 'transport': d.get('transport'),
                'connected': bool(d.get('connected'))}

    def _plan(self, data):
        profile_id = data.get('profile')
        if profile_id not in PROFILES:
            raise ValueError('Choose a Revive profile')
        row, rows, facts = self._context(data)
        if profile_id == 'app-kit' and isinstance(data.get('required_free'), int) and data['required_free'] > 0:
            facts['required_free'] = min(data['required_free'], 1 << 40)
        evaluated = C.evaluate(facts, profile_id)
        operations = [self._operation(op, evaluated, facts) for op in PROFILES[profile_id]['operations']]
        status = C.worst([o['status'] for o in operations])
        return {'schema': SCHEMA, 'profile': self._profile_view(profile_id), 'device': (row or {}).get('id'),
                'reason': None if row else ('no-connection' if not rows else 'device-not-selected'),
                'facts': self.present(facts), 'manual': facts['manual'], 'conflict': facts['identity']['conflict'],
                'checks': list(evaluated.values()), 'operations': operations, 'status': status,
                'created': now(), 'dry_run': True,
                'statement': 'This is a plan. Nothing was changed on the phone; copying is not installation.'}

    def _operation(self, op_id, evaluated, facts):
        spec = OPERATIONS[op_id]
        needed = [evaluated[c] for c in spec['requires'] if c in evaluated]
        status = C.worst([c['status'] for c in needed]) if needed else 'ready'
        recorded = facts['results'].get(op_id)
        return {'id': op_id, 'title': spec['title'], 'risk': spec['risk'], 'execution': spec['execution'],
                'prerequisites': [{'id': c['id'], 'status': c['status']} for c in needed],
                'source': spec['source'], 'version': None, 'sha256': None,
                'restore_point': spec['restore_point'], 'status': status,
                'note': spec.get('note'), 'result': recorded or {'result': 'not-run', 'at': None, 'source': None},
                'blocking': [c['id'] for c in needed if c['status'] in ('unsupported', 'needs-action')]}

    # ---- manual observations (stored separately, labelled manual) ---------------------------------
    def _need_device(self, data):
        row, _rows, facts = self._context(data)
        if row is None:
            raise ValueError('Select a connected phone first')
        return row, facts

    def _home(self, data):
        """Revive home: what is reachable for *this* phone, suggestions, one de-identified history."""
        row, rows, facts = self._context(data)
        saved = self._load('observations', facts['key']) if facts['key'] else {}
        ev = C.evaluate(facts, 'network-certs')
        prof = facts['identity']['profile']
        recs = list(self.services.recommendations(facts))
        tls = saved.get('tls', {})
        if ev['identity']['status'] == 'ready' and not any(str(v.get('state', '')).startswith('installed') for k, v in tls.items() if k in ('mbedtls-lib', 'ssl-patch')):
            recs.append({'id': 'current-tls-stack', 'area': 'network', 'title': {
                'en': 'Current network components (TLS 1.2/1.3) — prepare, then install on the phone',
                'ru': 'Актуальные сетевые компоненты (TLS 1.2/1.3) — подготовить и установить на телефоне'},
                'basis': 'author documentation; not tested on your phone', 'action': 'network-certs'})
        if ev['identity']['status'] == 'ready':
            recs.append({'id': 'app-kits', 'area': 'apps', 'title': {
                'en': 'Standard applications from verified kits', 'ru': 'Штатные приложения из проверенных наборов'},
                'basis': 'catalog evidence levels; nothing is installed automatically', 'action': 'app-kit'})
        evidence = [e for e in self.reborn.data['support_evidence'] if prof and e.get('profile') == prof['id']
                    and e.get('firmware') == facts['observed'].get('firmware')]
        if evidence:
            recs.append({'id': 'reborn-hybrid', 'area': 'cfw', 'title': {'en': 'Reborn Hybrid kit (support evidence recorded)', 'ru': 'Набор Reborn Hybrid (есть запись о поддержке)'},
                         'basis': 'support_evidence', 'action': 'reborn-n95'})
        history = []
        for key, entry in tls.items():
            history.append({'at': entry.get('at'), 'kind': 'tls', 'item': key, 'result': entry.get('state'), 'source': entry.get('source', 'symport')})
        for key, entry in saved.get('services', {}).items():
            history.append({'at': entry.get('at'), 'kind': 'service-setting', 'item': key, 'result': entry.get('result'), 'source': 'manual'})
        for key, entry in saved.get('reborn_stages', {}).items():
            history.append({'at': entry.get('at'), 'kind': 'reborn', 'item': key, 'result': entry.get('result'), 'source': 'manual'})
        for key, entry in saved.get('results', {}).items():
            history.append({'at': entry.get('at'), 'kind': 'operation', 'item': key, 'result': entry.get('result'), 'source': 'manual'})
        plans = self.safety.state({'device': (row or {}).get('id')})['plans'] if row else []
        for plan in plans:
            history.append({'at': plan['created'], 'kind': 'safety-plan', 'item': plan['scenario'], 'result': plan['status'], 'source': 'symport'})
        history.sort(key=lambda h: h['at'] or '', reverse=True)
        return {'device': (row or {}).get('id'), 'reason': None if row else ('no-connection' if not rows else 'device-not-selected'),
                'profile': prof['id'] if prof else None,
                'sections': [{'id': pid, 'available': pid in PROFILES} for pid in ('legacy-services', 'addons')],
                'recommendations': recs, 'history': history[:60],
                'statement': 'Suggestions only: nothing is installed, patched or marked fixed. History keeps what, when and the result; never setting values, messages or secrets.'}

    def _check_same_phone(self, plan: dict, row: dict) -> None:
        """Rollback keeps working after a firmware change but never on another phone."""
        device = plan['device']
        if row['id'] != device['id'] or row.get('rm') != device.get('rm') or row.get('model') != device.get('model'):
            raise ValueError('This plan belongs to another phone; nothing was changed')

    def _observe(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that this is what you observed on the phone')
        row, facts = self._need_device(data)
        saved = self._load('observations', facts['key'])
        kind = data.get('kind')
        if kind == 'rights':
            scope = data.get('scope')
            if scope not in RIGHTS_SCOPES:
                raise ValueError('Invalid rights scope')
            patches = data.get('patches', [])
            if not isinstance(patches, list) or len(patches) > 10:
                raise ValueError('Invalid patch list')
            saved['rights'] = {'scope': scope, 'patches': [_text(p, 60) for p in patches if _text(p, 60)],
                               'at': now(), 'source': 'manual'}
        elif kind == 'variant':
            saved['variant_confirmed'] = data.get('confirmed') is True
            saved['variant_label'] = _text(data.get('label'), 60)
        else:
            raise ValueError('Unknown observation')
        self._save('observations', facts['key'], saved)
        return self._inspect(dict(data, manual=data.get('manual')))

    def _record(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that you did this on the phone')
        op = data.get('operation')
        if op not in MANUAL_OPERATIONS:
            raise ValueError('Only on-phone steps can be recorded')
        if data.get('result') not in MANUAL_RESULTS:
            raise ValueError('Invalid result')
        row, facts = self._need_device(data)
        saved = self._load('observations', facts['key'])
        saved.setdefault('results', {})[op] = {'result': data['result'], 'at': now(), 'source': 'manual',
                                               'note': _text(data.get('note'), 200)}
        self._save('observations', facts['key'], saved)
        return {'operation': op, 'result': saved['results'][op]}

    def _baseline(self, data):
        row, facts = self._need_device(data)
        shown = self.present(facts)
        baseline = {'at': now(), 'device': row['id'], 'fingerprint': row.get('capability_fingerprint'),
                    'observed': facts['observed'],
                    'capabilities': {op: s['status'] for op, s in facts['capabilities'].items()},
                    'facts': shown}
        self._save('baselines', facts['key'], baseline)
        return {'baseline': baseline['at'], 'device': row['id']}

    def _verify(self, data):
        """Read-only re-check against the saved baseline. Differences are observations only."""
        row, facts = self._need_device(data)
        fresh = self.devices.execute({'action': 'capabilities', 'device': row['id']})['device']
        facts = self.facts(fresh, facts['manual'])
        base = facts['baseline']
        diff = []
        if base:
            for field in ('model', 'rm', 'product_code', 'firmware', 'transport', 'connection_kind'):
                if base['observed'].get(field) != facts['observed'].get(field):
                    diff.append({'field': field, 'before': base['observed'].get(field), 'after': facts['observed'].get(field)})
            b, a = base['observed'].get('free'), facts['observed'].get('free')
            if isinstance(b, int) and isinstance(a, int) and a != b:
                diff.append({'field': 'free', 'before': b, 'after': a, 'delta': a - b})
            for op, status in facts['capabilities'].items():
                before = base.get('capabilities', {}).get(op)
                if before and before != status['status']:
                    diff.append({'field': 'capability:' + op, 'before': before, 'after': status['status']})
        evaluated = C.evaluate(facts, 'post-check')
        operations = [self._operation(op, evaluated, facts) for op in PROFILES['post-check']['operations']]
        return {'schema': SCHEMA, 'device': row['id'], 'connected': bool(fresh.get('connected')),
                'baseline': base.get('at'), 'diff': diff,
                'phone_changed': bool(base) and base.get('fingerprint') != fresh.get('capability_fingerprint'),
                'checks': list(evaluated.values()), 'operations': operations,
                'statement': 'Differences are observations. They do not prove an installation or its success.'}
