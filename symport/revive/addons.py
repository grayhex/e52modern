"""Add-ons & Patch Manager (#39): compatibility-gated plans, a manual patch inventory, honest levels.

SymPort never installs an add-on or applies a patch. It decides, from device-read identity and your
own recorded observations, whether an add-on may even be *prepared*; only a pinned artifact (the TLS
components) can be copied, through the Recovery Safety Net. Everything else is a manual instruction
with the author's link. System patches are a closed category: no automation exists, and the
Patch Manager is read-only apart from the inventory *you* type in.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from pathlib import Path

from symport.catalog.service import now

from . import checks as C

DATA = Path(__file__).with_name('addons.json')
PATCH_STATES = ('applied', 'disabled', 'autostart', 'unknown')
ACTIONS = ('install', 'update', 'remove')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
LEVELS = ('downloaded', 'transferred', 'user-confirmed-installed', 'verified-on-device')
MARKS = ('installed', 'removed', 'failed')


def load() -> dict:
    document = json.loads(DATA.read_text(encoding='utf-8'))
    if document.get('schema') != 1:
        raise ValueError('Unsupported add-on registry')
    ids = [a['id'] for a in document['addons']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate add-on id')
    for a in document['addons']:
        if a['category'] not in document['categories']:
            raise ValueError('Unknown category: ' + a['id'])
        for ref in (*a['depends_on'], *a['conflicts_with']):
            if ref not in ids:
                raise ValueError('Unknown reference in ' + a['id'])
    return document


def text(value, limit):
    return re.sub(r'[\x00-\x1f\x7f]', ' ', value).strip()[:limit] if isinstance(value, str) else ''


class AddonManager:
    def __init__(self, service):
        self.service = service
        self.data = load()

    def _addon(self, aid):
        for a in self.data['addons']:
            if a['id'] == aid:
                return a
        raise ValueError('Unknown add-on')

    # ---- recorded observations -------------------------------------------------------------------
    def _saved(self, facts):
        return self.service._load('observations', facts['key']) if facts['key'] else {}

    def _installed(self, aid, saved) -> bool:
        a = self._addon(aid)
        if saved.get('addons', {}).get(aid, {}).get('state') == 'installed':
            return True
        ref = a['component_ref']
        if ref and ref['kind'] == 'tls':
            return saved.get('tls', {}).get(ref['id'], {}).get('state') == 'installed-reported'
        return False

    def _levels(self, addon, row, saved) -> dict:
        ref = addon['component_ref']
        downloaded = bool(ref and ref['kind'] == 'tls' and self.service.tls._cached(self.service.tls.components[ref['id']]))
        transferred = False
        if row and ref:
            for plan in self.service.safety.find_plans(row['id']):
                transferred = transferred or any(i.get('component') == ref['id'] and i.get('state') == 'written' and not i.get('removed')
                                                 for i in plan['items'])
        return {'downloaded': downloaded, 'transferred': transferred, 'user-confirmed-installed': self._installed(addon['id'], saved),
                'verified-on-device': 'not-available'}

    # ---- decision ------------------------------------------------------------------------------------
    def decide(self, addon, action, row, facts, saved) -> dict:
        blocks, warnings = [], []
        ev = C.evaluate(facts, 'network-certs')
        prof = facts['identity']['profile']
        opened = set(saved.get('open_categories', []))
        cat = self.data['categories'][addon['category']]

        def block(code, en, ru):
            blocks.append({'code': code, 'text': {'en': en, 'ru': ru}})

        if ev['identity']['status'] != 'ready':
            block('model-unidentified', 'The exact model must be read from the device.', 'Точная модель должна быть прочитана с устройства.')
        elif prof['id'] not in addon['targets']:
            block('model-not-targeted', f"{prof['name']} is not a confirmed target of this add-on.", f"{prof.get('name_ru') or prof['name']} не входит в подтверждённые цели этого дополнения.")
        if prof and registry_has_rms(prof['id']) and not facts['observed'].get('rm'):
            block('rm-unknown', 'The device did not report its RM code.', 'Устройство не сообщило код RM.')
        if action == 'remove':
            return {'decision': 'manual-only' if not blocks else 'blocked', 'blocks': blocks, 'warnings': warnings,
                    'steps': [addon['uninstall']], 'rollback': addon['uninstall'],
                    'statement': 'SymPort cannot remove an add-on or restore a system DLL after its SIS is gone.'}
        if cat['closed_by_default'] and addon['category'] not in opened:
            block('category-closed', 'System patches are a closed category: open it explicitly first.', 'Системные патчи — закрытая категория: сначала откройте её явно.')
        firmware = facts['observed'].get('firmware')
        if addon['firmware']['verified']:
            if firmware not in addon['firmware']['verified']:
                block('firmware-unconfirmed', 'The device firmware is not among the verified versions.', 'Прошивка устройства не входит в проверенные версии.')
        elif addon['risk'] == 'high':
            block('firmware-unverified', 'No firmware version has been verified for this high-risk add-on.', 'Для этого высокорискового дополнения не проверена ни одна версия прошивки.')
        else:
            warnings.append('firmware-not-verified')
        if not addon['licence'].get('spdx'):
            block('licence-missing', 'No confirmed licence or redistribution right.', 'Нет подтверждённой лицензии или права распространения.')
        if not addon['version_confirmed']:
            block('version-unconfirmed', 'The version is not confirmed.', 'Версия не подтверждена.')
        for dep in addon['depends_on']:
            if not self._installed(dep, saved):
                block('dependency-missing:' + dep, f'Requires {dep}, which is not recorded as installed.', f'Требуется {dep}, который не отмечен как установленный.')
        for other in addon['conflicts_with']:
            if self._installed(other, saved):
                block('conflict:' + other, f'Conflicts with {other}, which is recorded as installed.', f'Конфликтует с {other}, который отмечен как установленный.')
        if addon.get('autostart'):
            via = addon['autostart']['claimed_by_author']
            if any(p['state'] == 'autostart' and p.get('autostart_via') == via for p in saved.get('patches', [])):
                block('autostart-conflict', f'Another recorded patch already starts through {via}.', f'Другой записанный патч уже запускается через {via}.')
        if addon['risk'] == 'high':
            rights = facts.get('rights')
            if not rights or rights['scope'] != 'device':
                block('privileges-missing', 'Device-level installation rights are not recorded (your own observation).', 'Права установки уровня устройства не записаны (ваше наблюдение).')
            if not saved.get('data_backup'):
                block('incomplete-backup', 'Record your own backup statement first.', 'Сначала запишите подтверждение вашей резервной копии.')
        ref = addon['component_ref']
        if ref is None or ref['kind'] != 'tls':
            mode = 'manual-only'
        else:
            mode = 'ready-to-prepare'
        decision = 'blocked' if blocks else mode
        # A missing licence/version/target only blocks automation; the author link and manual text stay visible.
        return {'decision': decision, 'blocks': blocks, 'warnings': warnings, 'steps': [addon['install']], 'rollback': addon['uninstall'],
                'statement': 'Preparation only: SymPort never installs or patches. ' + ('The file can be copied through the Safety Net.' if decision == 'ready-to-prepare' else 'Follow the author\'s instructions yourself.')}

    # ---- actions ---------------------------------------------------------------------------------------
    def state(self, data):
        row, rows, facts = self.service._context(data)
        saved = self._saved(facts)
        items = []
        for a in self.data['addons']:
            plan = self.decide(a, 'install', row, facts, saved) if row else None
            record = saved.get('addons', {}).get(a['id'])
            update = bool(record and record.get('version') and a['version'] and record['version'] != a['version'])
            items.append({**{k: a[k] for k in ('id', 'title', 'category', 'risk', 'source', 'licence', 'version', 'version_confirmed',
                                               'targets', 'depends_on', 'conflicts_with', 'install', 'uninstall', 'firmware')},
                          'mode': 'pinned-artifact' if a['component_ref'] and a['component_ref']['kind'] == 'tls' else 'manual-only',
                          'decision': plan, 'levels': self._levels(a, row, saved), 'record': record, 'update_available': update})
        patches = saved.get('patches', [])
        return {'device': (row or {}).get('id'), 'reason': None if row else ('no-connection' if not rows else 'device-not-selected'),
                'categories': {k: {**v, 'open': k in saved.get('open_categories', [])} for k, v in self.data['categories'].items()},
                'addons': items, 'patches': patches, 'patch_warnings': self.patch_warnings(patches, row),
                'patch_manager': {'agent_inventory': 'not-available', 'writes': 'disabled',
                                  'note': 'No agent reads patches from the phone; the inventory below is what you typed. Applying, autostart and removal are disabled: there is no proven API or recovery.'},
                'statement': self.data['note']}

    def plan(self, data):
        a = self._addon(data.get('addon'))
        action = data.get('action_kind', 'install')
        if action not in ACTIONS:
            raise ValueError('Invalid action')
        row, _rows, facts = self.service._context(data)
        if row is None:
            raise ValueError('Select a connected phone first')
        saved = self._saved(facts)
        return {'addon': a['id'], 'action': action, **self.decide(a, action, row, facts, saved), 'dry_run': True,
                'levels': self._levels(a, row, saved)}

    def prepare(self, data):
        a = self._addon(data.get('addon'))
        plan = self.plan(dict(data, action_kind='install'))
        if plan['decision'] != 'ready-to-prepare':
            raise ValueError('Not preparable: ' + (', '.join(b['code'] for b in plan['blocks']) or plan['decision']))
        return self.service.safety.plan_action({'scenario': 'tls', 'device': data.get('device'), 'manual': data.get('manual'),
                                                'components': [a['component_ref']['id']]})

    def open_category(self, data):
        cat = data.get('category')
        if cat not in self.data['categories'] or not self.data['categories'][cat]['closed_by_default']:
            raise ValueError('Only closed categories can be opened')
        if data.get('confirm') is not True or data.get('acknowledge') is not True:
            raise ValueError('Confirm and acknowledge that SymPort offers instructions only for system patches')
        row, facts = self.service._need_device(data)
        saved = self._saved(facts)
        saved['open_categories'] = sorted(set(saved.get('open_categories', [])) | {cat})
        self.service._save('observations', facts['key'], saved)
        return {'open_categories': saved['open_categories']}

    def mark(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that this is what you observed on the phone')
        a = self._addon(data.get('addon'))
        state = data.get('state')
        if state not in MARKS:
            raise ValueError('Invalid state')
        row, facts = self.service._need_device(data)
        saved = self._saved(facts)
        saved.setdefault('addons', {})[a['id']] = {'state': state, 'version': a['version'] if state == 'installed' else None, 'at': now(), 'source': 'manual'}
        self.service._save('observations', facts['key'], saved)
        return {'addon': a['id'], 'record': saved['addons'][a['id']]}

    def verify_file(self, data):
        a = self._addon(data.get('addon'))
        try:
            raw = base64.b64decode(data.get('content', ''), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('broken-package: content is not valid base64') from exc
        digest = hashlib.sha256(raw).hexdigest()
        ref = a['component_ref']
        if not ref or ref['kind'] != 'tls':
            return {'addon': a['id'], 'sha256': digest, 'status': 'cannot-verify', 'reason': 'No pinned artifact exists for this add-on; the hash is shown for your records only.'}
        pinned = self.service.tls.components[ref['id']]['sha256']
        if digest != pinned:
            raise ValueError('hash-mismatch: this file is not the pinned build; transfer is blocked')
        return {'addon': a['id'], 'sha256': digest, 'status': 'matches-pin'}

    # ---- Patch Manager inventory (manual) ------------------------------------------------------------------
    def patch_save(self, data):
        name, state = text(data.get('name'), 80), data.get('state')
        if not name or state not in PATCH_STATES:
            raise ValueError('A patch needs a name and a valid state')
        original = str(data.get('original_sha256') or '').lower()
        if original and not HEX64.fullmatch(original):
            raise ValueError('The original binary hash must be a SHA-256')
        row, facts = self.service._need_device(data)
        saved = self._saved(facts)
        patches = saved.setdefault('patches', [])
        if len(patches) >= 50:
            raise ValueError('Inventory is limited to 50 patches')
        entry = {'id': secrets.token_hex(6), 'name': name, 'source': text(data.get('source'), 200), 'original_sha256': original or None,
                 'state': state, 'autostart_via': text(data.get('autostart_via'), 40) or None,
                 'depends_on': [text(x, 80) for x in (data.get('depends_on') or [])][:10] if isinstance(data.get('depends_on'), list) else [],
                 'risk': data.get('risk') if data.get('risk') in ('low', 'medium', 'high') else 'high',
                 'notes': text(data.get('notes'), 300), 'recorded_for': {k: facts['observed'].get(k) for k in ('model', 'rm', 'firmware')},
                 'at': now(), 'source_of_entry': 'manual'}
        patches.append(entry)
        self.service._save('observations', facts['key'], saved)
        return {'patch': entry, 'warnings': self.patch_warnings(patches, row)}

    def patch_delete(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm removing this inventory entry (it does not touch the phone)')
        row, facts = self.service._need_device(data)
        saved = self._saved(facts)
        before = len(saved.get('patches', []))
        saved['patches'] = [p for p in saved.get('patches', []) if p['id'] != data.get('id')]
        if len(saved['patches']) == before:
            raise ValueError('Unknown inventory entry')
        self.service._save('observations', facts['key'], saved)
        return {'removed': data['id']}

    @staticmethod
    def patch_warnings(patches, row) -> list[dict]:
        out = []
        starters = {}
        names = {p['name'].lower() for p in patches}
        for p in patches:
            if p['state'] == 'autostart' and p.get('autostart_via'):
                starters.setdefault(p['autostart_via'], []).append(p['name'])
            for dep in p.get('depends_on', []):
                if dep.lower() not in names:
                    out.append({'code': 'dependency-missing', 'patch': p['name'], 'detail': dep})
            if row and p['recorded_for']['firmware'] and p['recorded_for']['firmware'] != row.get('firmware'):
                out.append({'code': 'recorded-for-other-firmware', 'patch': p['name']})
            if p['state'] == 'unknown':
                out.append({'code': 'state-unknown', 'patch': p['name']})
        for via, who in starters.items():
            if len(who) > 1:
                out.append({'code': 'autostart-conflict', 'patch': ', '.join(who), 'detail': via})
        return out


def registry_has_rms(profile_id: str) -> bool:
    from symport.phone.registry import registry
    return bool(registry().get(profile_id, {}).get('rms'))
