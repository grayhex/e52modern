"""Recovery Safety Net (#36): plan → snapshot → apply → postflight → rollback → report.

One mechanism for every Revive scenario that copies files to a phone. It is deliberately modest:

* a *snapshot* records only what is readable over the current transport (target tree, hashes of
  existing files at the targets, a PIM export and package inventory where those capabilities were
  actually verified). It never claims to restore a phone: an SD-card copy cannot restore firmware
  or phone memory, and SymPort cannot back up system firmware at all;
* a saved plan is bound to the connection fingerprint, model, RM, exact firmware and the file
  hashes. A different phone, other firmware or a changed file refuses the plan instead of reusing it;
* rollback removes only files this plan created, only when the bytes still match, one file at a time
  (never recursive, never an unknown system file);
* nothing here deletes, reflashes or changes system partitions.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets

from symport.catalog.service import now

from . import checks as C

SCHEMA = 'symport.safety/1'
PLAN_ID = re.compile(r'^[0-9a-f]{32}$')
ITEM_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,90}$')
CHECKLIST = ('boot', 'connectivity', 'wifi', 'files', 'contacts', 'apps', 'https', 'errors')
CHECK_RESULTS = ('pass', 'fail', 'not-tested')
FOLDER_RE = re.compile(r'^SymPort-[A-Za-z0-9-]{1,40}$')
STATEMENT = ('A snapshot holds only what SymPort could read over this connection. It cannot restore the phone: '
             'an SD-card copy never restores firmware or phone memory, and system firmware cannot be backed up by SymPort.')
ROLLBACK_SCOPE = ('Only files created by this plan are removed, one by one, and only when their bytes are unchanged. '
                  'Anything you installed or changed on the phone, folders and every system file stay as they are.')
EXPORT_FIELDS = ('schema', 'id', 'scenario', 'label', 'created', 'status')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class SafetyNet:
    def __init__(self, service):
        self.service = service
        self.root = service.root / 'safety'
        # scenario name -> callable(row, facts, plan) -> list[{'code','text'}] of unmet *conditions*
        self.gates: dict = {}

    # ---- artifact + plan storage -----------------------------------------------------------------
    def put_artifact(self, raw: bytes) -> str:
        digest = sha(raw)
        path = self.root / 'artifacts' / digest
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.exists():
            path.write_bytes(raw)
        return digest

    def artifact(self, digest: str) -> bytes | None:
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            return None
        path = self.root / 'artifacts' / digest
        try:
            raw = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        except OSError:
            return None
        return raw if raw is not None and sha(raw) == digest else None

    def _plan_path(self, plan_id):
        if not isinstance(plan_id, str) or not PLAN_ID.fullmatch(plan_id):
            raise ValueError('Invalid plan id')
        return self.root / 'plans' / (plan_id + '.json')

    def load(self, plan_id) -> dict:
        try:
            return json.loads(self._plan_path(plan_id).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ValueError('Unknown plan') from exc

    def save(self, plan: dict) -> dict:
        from symport.catalog.service import save
        save(self._plan_path(plan['id']), plan)
        return plan

    def event(self, plan, action, status, **extra):
        plan['events'].append({'at': now(), 'action': action, 'status': status, **extra})
        return self.save(plan)

    # ---- helpers ---------------------------------------------------------------------------------
    @staticmethod
    def _binding(row: dict, key: str, items: list[dict]) -> dict:
        return {'device_key': key, 'fingerprint': row.get('capability_fingerprint'), 'model': row.get('model'),
                'rm': row.get('rm'), 'firmware': row.get('firmware'),
                'files': sorted(i['sha256'] for i in items)}

    def _fresh_context(self, plan):
        row, rows = self.service._row(plan['device']['id'])
        if row is None:
            raise ValueError('The phone of this plan is not connected')
        facts = self.service.facts(row, {'model': '', 'rm': '', 'firmware': ''})
        return row, facts

    def _check_binding(self, plan, row, facts):
        wanted = plan['binding']
        problems = []
        if facts['key'] != wanted['device_key'] or row.get('capability_fingerprint') != wanted['fingerprint']:
            problems.append('phone-changed')
        if row.get('rm') != wanted['rm'] or row.get('model') != wanted['model']:
            problems.append('model-or-rm-changed')
        if row.get('firmware') != wanted['firmware']:
            problems.append('firmware-changed')
        for item in plan['items']:
            raw = self.artifact(item['sha256'])
            if raw is None:
                problems.append('artifact-missing:' + item['name'])
            elif len(raw) != item['size']:
                problems.append('artifact-changed:' + item['name'])
        if problems:
            raise ValueError('The saved plan no longer matches this phone or these files (' + ', '.join(problems)
                             + '). Create a new plan; confirmed plans are never reused blindly.')

    def _list(self, device, folder):
        try:
            entries = self.service.devices.execute({'action': 'list', 'device': device, 'path': folder})['entries']
        except (ValueError, OSError):
            return None  # folder missing or not listable
        return {e['name']: e for e in entries}

    # ---- planning --------------------------------------------------------------------------------
    def build_plan(self, row, facts, *, scenario: str, label: str, folder: str, items: list[dict], risk: dict,
                   restore: dict, phone_actions: list[dict], extra: dict | None = None) -> dict:
        if not FOLDER_RE.fullmatch(folder):
            raise ValueError('Invalid target folder')
        norm = []
        for item in items:
            if not ITEM_NAME.fullmatch(item['name']) or self.artifact(item['sha256']) is None:
                raise ValueError('Plan items must be stored, hashed files with safe names')
            norm.append({'name': item['name'], 'path': f"{folder}/{item['name']}", 'sha256': item['sha256'],
                         'size': item['size'], 'state': 'planned', 'created': False, 'component': item.get('component')})
        if len({i['name'] for i in norm}) != len(norm):
            raise ValueError('Duplicate file names in a plan')
        listing = self._list(row['id'], folder)
        overwrites, conflicts = [], []
        for item in norm:
            existing = (listing or {}).get(item['name'])
            if not existing:
                continue
            try:
                got = self.service.devices.execute({'action': 'download', 'device': row['id'], 'path': item['path']})
                same = sha(base64.b64decode(got['content'], validate=True)) == item['sha256']
            except (ValueError, OSError):
                same = False
            (overwrites if same else conflicts).append(item['path'])
            item['state'] = 'identical-preexisting' if same else 'conflict'
        free = facts['observed'].get('free')
        total = sum(i['size'] for i in norm if i['state'] == 'planned')
        plan = {
            'schema': SCHEMA, 'id': secrets.token_hex(16), 'scenario': scenario, 'label': str(label)[:120],
            'created': now(), 'status': 'planned',
            'device': {'id': row['id'], 'key': facts['key'], 'fingerprint': row.get('capability_fingerprint'),
                       'model': row.get('model'), 'rm': row.get('rm'), 'firmware': row.get('firmware'),
                       'transport': row.get('transport'), 'connection_kind': row.get('connection_kind')},
            'binding': self._binding(row, facts['key'], norm),
            'folder': folder, 'items': norm,
            'dry_run': {'new_files': sum(i['state'] == 'planned' for i in norm), 'bytes': total,
                        'folder_exists': listing is not None, 'identical_preexisting': overwrites, 'conflicts': conflicts,
                        'overwrites': [], 'free_before': free,
                        'free_after': free - total if isinstance(free, int) else None,
                        'note': 'SymPort never overwrites a different file; a conflict stops the transfer.'},
            'risk': risk, 'restore': restore, 'phone_actions': phone_actions,
            'snapshot': None, 'applied': False, 'rollback': None, 'checklist': {}, 'postflight': None, 'events': [],
            **(extra or {}),
        }
        plan['risk']['conflicts'] = bool(conflicts)
        return self.event(plan, 'plan', 'dry-run')

    def plan_view(self, plan, row=None, facts=None) -> dict:
        """The plan with a live view of which blocking risks are still open."""
        view = {k: v for k, v in plan.items() if k not in ('events',)}
        view['events'] = plan['events'][-30:]
        view['blocking'] = self.open_blocking(plan, row, facts)
        view['statement'] = STATEMENT
        view['rollback_scope'] = ROLLBACK_SCOPE
        return view

    def open_blocking(self, plan, row=None, facts=None) -> list[dict]:
        acked = set(plan.get('acknowledged', []))
        out = []
        for risk in plan['risk'].get('blocking', []):
            if risk.get('satisfied_by') == 'acknowledgement' and risk['code'] in acked:
                continue
            if risk.get('satisfied_by') == 'acknowledgement':
                out.append({**risk, 'open': True})
        if plan['dry_run']['conflicts']:
            out.append({'code': 'file-conflict', 'satisfied_by': 'none',
                        'text': {'en': 'A different file already exists at a target path; SymPort will not overwrite it.',
                                 'ru': 'По целевому пути уже лежит другой файл; SymPort его не перезапишет.'}, 'open': True})
        if row is not None and facts is not None:
            gate = self.gates.get(plan['scenario'])
            for unmet in (gate(row, facts, plan) if gate else []):
                out.append({**unmet, 'satisfied_by': 'condition', 'open': True})
        return out

    # ---- actions ---------------------------------------------------------------------------------
    def execute(self, action, data):
        handler = {
            'safety-state': self.state, 'safety-plan': self.plan_action, 'safety-snapshot': self.snapshot,
            'safety-apply': self.apply, 'safety-rollback': self.rollback, 'safety-postflight': self.postflight,
            'safety-checklist': self.checklist, 'safety-export': self.export, 'safety-ack': self.ack,
            'safety-view': self.view,
        }[action]
        return handler(data)

    def state(self, data):
        plans = []
        base = self.root / 'plans'
        for path in sorted(base.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:30] if base.is_dir() else []:
            try:
                plan = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if data.get('device') and plan['device']['id'] != data['device']:
                continue
            plans.append({k: plan[k] for k in ('id', 'scenario', 'label', 'created', 'status')}
                         | {'items': len(plan['items']), 'risk': plan['risk']['level']})
        return {'schema': SCHEMA, 'plans': plans, 'checklist_items': list(CHECKLIST), 'statement': STATEMENT,
                'kinds': {'target-tree': 'readable', 'pim-export': 'only when contacts.read is verified',
                          'sis-collection': 'only on enrolled volumes', 'card-copy': 'not performed',
                          'firmware': 'not available'}}

    def plan_action(self, data):
        """Create a plan for a registered scenario; files come from SymPort's own stores only."""
        builder = self.service.scenarios.get(data.get('scenario'))
        if builder is None:
            raise ValueError('Unknown scenario')
        row, facts = self.service._need_device(data)
        plan = builder(row, facts, data)
        return self.plan_view(plan, row, facts)

    def _plan_and_context(self, data):
        plan = self.load(data.get('plan'))
        row, facts = self._fresh_context(plan)
        return plan, row, facts

    def view(self, data):
        plan = self.load(data.get('plan'))
        row, _rows = self.service._row(plan['device']['id'])
        facts = self.service.facts(row, {'model': '', 'rm': '', 'firmware': ''}) if row else None
        return self.plan_view(plan, row, facts)

    def ack(self, data):
        plan = self.load(data.get('plan'))
        if data.get('confirm') is not True:
            raise ValueError('Confirm the acknowledgement')
        known = {r['code'] for r in plan['risk'].get('blocking', []) if r.get('satisfied_by') == 'acknowledgement'}
        codes = data.get('codes')
        if not isinstance(codes, list) or not codes or any(c not in known for c in codes):
            raise ValueError('Unknown risk acknowledgement')
        plan['acknowledged'] = sorted(set(plan.get('acknowledged', [])) | set(codes))
        self.event(plan, 'acknowledge', 'recorded', codes=plan['acknowledged'])
        row, facts = self._fresh_context(plan)
        return self.plan_view(plan, row, facts)

    def snapshot(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm taking the snapshot')
        plan, row, facts = self._plan_and_context(data)
        if plan['status'] not in ('planned', 'snapshotted'):
            raise ValueError('A snapshot belongs to a plan that has not been applied')
        self._check_binding(plan, row, facts)
        device = row['id']
        manager = self.service.devices
        tree = self._list(device, plan['folder'])
        hashes = {}
        for item in plan['items']:
            if tree and item['name'] in tree:
                try:
                    raw = base64.b64decode(manager.execute({'action': 'download', 'device': device, 'path': item['path']})['content'], validate=True)
                    hashes[item['path']] = sha(raw)
                except (ValueError, OSError):
                    hashes[item['path']] = None
        caps = facts['capabilities']
        kinds = {'target-tree': 'done' if tree is not None else 'folder-missing', 'target-hashes': 'done' if hashes else 'nothing-to-hash',
                 'card-copy': 'not-performed', 'firmware': 'not-available'}
        pim = None
        if (caps.get('contacts.read') or {}).get('status') == 'available':
            try:
                contacts = manager.execute({'action': 'contacts-read', 'device': device})
                body = json.dumps(contacts, ensure_ascii=False, sort_keys=True).encode()
                directory = self.root / 'snapshots' / plan['id']
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                target = directory / 'contacts.json'
                target.write_bytes(body)
                target.chmod(0o600)
                pim = {'contacts_sha256': sha(body), 'count': len(contacts.get('contacts', [])) if isinstance(contacts, dict) else None}
                kinds['pim-export'] = 'done'
            except (ValueError, OSError):
                kinds['pim-export'] = 'failed'
        else:
            kinds['pim-export'] = 'not-available: contacts.read not verified'
        if (caps.get('files.list') or {}).get('status') == 'available':
            try:
                inv = manager.execute({'action': 'apps-inventory', 'device': device})
                packages = inv.get('packages', []) if isinstance(inv, dict) else []
                kinds['sis-collection'] = f'{len(packages)} package files listed (not an installed-app registry)'
            except (ValueError, OSError):
                kinds['sis-collection'] = 'not-available'
        else:
            kinds['sis-collection'] = 'not-available'
        plan['snapshot'] = {
            'at': now(), 'kinds': kinds, 'pim': pim,
            'tree': sorted(tree) if tree else [], 'hashes': hashes,
            'facts': {'model': row.get('model'), 'rm': row.get('rm'), 'firmware': row.get('firmware'),
                      'transport': row.get('transport'), 'free': facts['observed'].get('free'),
                      'capabilities': {op: s['status'] for op, s in caps.items()}},
            'complete_phone_backup': False, 'statement': STATEMENT,
        }
        plan['status'] = 'snapshotted'
        self.event(plan, 'snapshot', 'saved-partial')
        return self.plan_view(plan, row, facts)

    def apply(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm copying the planned files')
        plan, row, facts = self._plan_and_context(data)
        if plan['status'] == 'transferred-awaiting-manual-install' or plan.get('applied') and plan['status'] != 'interrupted':
            raise ValueError('This plan was already applied; create a new plan to repeat it')
        if plan['status'] not in ('snapshotted', 'interrupted'):
            raise ValueError('Take the snapshot first')
        self._check_binding(plan, row, facts)
        blocking = self.open_blocking(plan, row, facts)
        if blocking:
            raise ValueError('Blocked: ' + '; '.join(b['code'] for b in blocking))
        evaluated = C.evaluate(dict(facts, required_free=plan['dry_run']['bytes'] * 2), 'network-certs')
        for gate in ('connection', 'files', 'transfer'):
            if evaluated[gate]['status'] in ('unsupported', 'needs-action', 'unknown'):
                raise ValueError(f"Blocked: {gate}: {evaluated[gate]['reason']['en']}")
        manager, device = self.service.devices, row['id']
        plan['status'] = 'applying'
        plan['applied'] = True
        self.event(plan, 'apply', 'started')
        try:
            try:
                manager.execute({'action': 'mkdir', 'device': device, 'path': plan['folder'], 'confirm': True})
            except (ValueError, OSError):
                pass
            for item in plan['items']:
                if item['state'] in ('written', 'identical-preexisting'):
                    continue
                raw = self.artifact(item['sha256'])
                try:
                    manager.execute({'action': 'upload', 'device': device, 'path': item['path'],
                                     'content': base64.b64encode(raw).decode(), 'confirm': True})
                    item['created'] = True
                except FileExistsError:
                    got = manager.execute({'action': 'download', 'device': device, 'path': item['path']})
                    if sha(base64.b64decode(got['content'], validate=True)) == item['sha256']:
                        item['state'] = 'identical-preexisting'
                        self.save(plan)
                        continue
                    item['state'] = 'conflict'
                    raise ValueError('conflict: a different file already exists at ' + item['path'] + '; it was not overwritten') from None
                echoed = manager.execute({'action': 'download', 'device': device, 'path': item['path']})
                written = sha(base64.b64decode(echoed['content'], validate=True))
                item['written_sha256'] = written
                if written != item['sha256']:
                    item['state'] = 'hash-mismatch'
                    raise ValueError('Read-back SHA-256 mismatch for ' + item['name'] + '; the copy is not trusted')
                item['state'] = 'written'
                self.save(plan)
        except (ValueError, OSError) as exc:
            plan['status'] = 'interrupted'
            self.event(plan, 'apply', 'interrupted', error=str(exc)[:200])
            raise
        plan['status'] = 'transferred-awaiting-manual-install'
        self.event(plan, 'apply', 'transferred-not-installed')
        return self.plan_view(plan, row, facts)

    def rollback(self, data):
        plan = self.load(data.get('plan'))
        row, _rows = self.service._row(plan['device']['id'])
        removable = [i for i in plan['items'] if i.get('created') and not i.get('removed')]
        preview = {'plan': plan['id'], 'scope': ROLLBACK_SCOPE, 'files': [{'path': i['path'], 'name': i['name']} for i in removable],
                   'system_restore': 'unsupported', 'installed_software': 'not-restored'}
        if data.get('confirm') is not True:
            return {**preview, 'dry_run': True}
        if row is None:
            raise ValueError('The phone of this plan is not connected')
        self.service._check_same_phone(plan, row)
        removed, conflicts, gone = [], [], []
        for item in removable:
            try:
                got = self.service.devices.execute({'action': 'download', 'device': row['id'], 'path': item['path']})
            except (ValueError, OSError):
                item['removed'] = True
                gone.append(item['path'])
                continue
            current = sha(base64.b64decode(got['content'], validate=True))
            if current not in (item['sha256'], item.get('written_sha256')):
                conflicts.append(item['path'])
                continue
            self.service.devices.execute({'action': 'delete', 'device': row['id'], 'path': item['path'], 'confirm': True})
            item['removed'] = True
            removed.append(item['path'])
        plan['rollback'] = {'at': now(), 'removed': removed, 'already_gone': gone, 'conflicts': conflicts,
                            'system_restored': False, 'folder_left': plan['folder']}
        plan['status'] = 'rollback-partial' if conflicts else 'rolled-back'
        self.event(plan, 'rollback', plan['status'])
        return {**preview, 'dry_run': False, **plan['rollback'], 'status': plan['status']}

    def postflight(self, data):
        plan = self.load(data.get('plan'))
        row, _ = self.service._row(plan['device']['id'])
        if row is None:
            return {'plan': plan['id'], 'connected': False, 'checks': [{'id': 'connection', 'status': 'needs-action'}],
                    'statement': 'The phone is not connected; nothing was verified.'}
        fresh = self.service.devices.execute({'action': 'capabilities', 'device': row['id']})['device']
        before = (plan.get('snapshot') or {}).get('facts') or {}
        diff = []
        for field in ('model', 'rm', 'firmware', 'transport'):
            if field in before and before[field] != fresh.get(field):
                diff.append({'field': field, 'before': before[field], 'after': fresh.get(field)})
        files = []
        for item in plan['items']:
            if not item.get('created') and item['state'] != 'identical-preexisting':
                continue
            try:
                got = self.service.devices.execute({'action': 'download', 'device': row['id'], 'path': item['path']})
                present = sha(base64.b64decode(got['content'], validate=True)) == item['sha256']
                files.append({'path': item['path'], 'state': 'present-hash-match' if present else 'present-hash-differs'})
            except (ValueError, OSError):
                files.append({'path': item['path'], 'state': 'missing'})
        result = {'plan': plan['id'], 'connected': bool(fresh.get('connected')), 'at': now(),
                  'identity': 'unchanged' if not diff else 'changed', 'diff': diff, 'files': files,
                  'checklist': plan.get('checklist', {}), 'installation': 'unknown',
                  'statement': 'Automated checks cover what SymPort can read. Boot, Wi-Fi, apps and HTTPS are what you report in the checklist; '
                               'nothing here proves an installation or its success.'}
        plan['postflight'] = {k: result[k] for k in ('at', 'identity', 'diff', 'files')}
        self.event(plan, 'postflight', 'read-only')
        return result

    def checklist(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that this is what you observed')
        plan = self.load(data.get('plan'))
        item, result = data.get('item'), data.get('result')
        if item not in CHECKLIST or result not in CHECK_RESULTS:
            raise ValueError('Invalid checklist entry')
        plan['checklist'][item] = {'result': result, 'at': now(), 'source': 'manual'}
        self.event(plan, 'checklist', 'manual-observation', item=item, result=result)
        return {'plan': plan['id'], 'checklist': plan['checklist']}

    def export(self, data):
        """De-identified report: no IMEI, contact data, messages, secrets or snapshot payloads."""
        plan = self.load(data.get('plan'))
        snap = plan.get('snapshot') or {}
        report = {k: plan[k] for k in EXPORT_FIELDS}
        report.update({
            'device': {k: plan['device'].get(k) for k in ('model', 'rm', 'firmware', 'transport', 'connection_kind', 'fingerprint')},
            'folder': plan['folder'],
            'items': [{k: i.get(k) for k in ('name', 'path', 'sha256', 'size', 'state', 'created', 'removed')} for i in plan['items']],
            'dry_run': plan['dry_run'], 'risk': plan['risk'], 'restore': plan['restore'],
            'acknowledged': plan.get('acknowledged', []),
            'snapshot': {'at': snap.get('at'), 'kinds': snap.get('kinds'), 'tree': snap.get('tree'),
                         'hashes': snap.get('hashes'), 'complete_phone_backup': False,
                         'pim': {'count': (snap.get('pim') or {}).get('count')} if snap.get('pim') else None},
            'rollback': plan.get('rollback'), 'postflight': plan.get('postflight'), 'checklist': plan.get('checklist'),
            'events': [{k: e.get(k) for k in ('at', 'action', 'status')} for e in plan['events']],
            'statement': STATEMENT, 'physical_device_verification': 'not-performed',
        })
        text = json.dumps(report, ensure_ascii=False, indent=2)
        return {'name': f"symport-safety-{plan['id'][:8]}.json", 'mime': 'application/json',
                'content': base64.b64encode(text.encode()).decode(), 'sha256': sha(text.encode())}
