"""Nokia N95 — Reborn Hybrid CFW (alpha) wizard (#35).

What this is: the author's SIS mod kit, installed *on the phone* over a stock S60v3 FP1 firmware.
What SymPort does: preflight from real device data, manual import and validation of the file you
obtained from the author, a locally confirmed hash pin, backup attestation, a Safety Net plan with
separate consents, a verified file copy and a postflight record. What it never does: download the
kit (redistribution is unconfirmed), install it, patch the system, jailbreak or flash. ``Success``
is only an installation *you* confirm on the phone.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from symport.catalog.packages import MAX_PACKAGE, validate_package
from symport.catalog.service import now
from symport.deps.analysis import analyze_package
from symport.inspector.signatures import inspect_signatures
from symport.sis.reader import inspect

from . import checks as C

DATA = Path(__file__).with_name('reborn.json')
FOLDER = 'SymPort-Reborn'
SCENARIO = 'reborn-n95'
STAGES = ('installer-opened', 'installed', 'rebooted', 'network-works')
# Post-installation checks the user performs on the phone; evidence is always "user-reported".
POSTCHECKS = ('calls-sms', 'file-manager', 'wifi', 'https-on-phone', 'alt-links', 'launch-uninstall')
# Changes the author *describes*. SymPort looks only at file names inside the package: a match is a
# lead, never proof that the behaviour exists; no match means "not detected", not "absent".
CLAIMS = {
    'ssl-ca': re.compile(r'cacert|ca-?cert|certstore|mozilla|ssl|cert', re.I),
    'uaprof': re.compile(r'uaprof|\brdf\b|\.rdf', re.I),
    'connectivity-check': re.compile(r'conntest|connectivity', re.I),
    'dead-services': re.compile(r'podcast|\bstore\b|ovi|dummy', re.I),
    'file-manager': re.compile(r'fileman|filemanager', re.I),
    'n-gage': re.compile(r'n-?gage', re.I),
}
# Files that the separate TLS stack (symbian-tls / mbedtls) also owns.
TLS_OVERLAP = ('ssl.dll', 'mbedtls.dll', 'mbedtls.dso')
STAGE_RESULTS = ('pass', 'fail', 'not-tested')
REGIONAL = ('RM-160', 'RM-245')
HIGH_RISK_PATH = re.compile(r'^(?:[a-z!]:)?\\(?:sys|resource|private|system)\\', re.I)


def load() -> dict:
    document = json.loads(DATA.read_text(encoding='utf-8'))
    if document.get('schema') != 1:
        raise ValueError('Unsupported Reborn data')
    return document


def message(en, ru):
    return {'en': en, 'ru': ru}


def components(raw: bytes) -> list[dict]:
    """Preview of what the SIS would put on the phone; high-risk entries need a separate consent."""
    info = inspect(raw)
    rows = []
    for f in info['files'][:300]:
        target = str(f['target'])
        suffix = target.lower().rsplit('.', 1)[-1] if '.' in target else ''
        reasons = []
        if HIGH_RISK_PATH.match(target):
            reasons.append('system-or-private-path')
        if suffix in ('exe', 'dll', 'rsc', 'fxt'):
            reasons.append('executable-or-system-resource')
        rows.append({'target': target, 'size': f.get('uncompressed_length'), 'hash_ok': f.get('hash_ok'),
                     'high_risk': bool(reasons), 'reasons': reasons})
    return rows


def modifications(files: list[dict]) -> list[dict]:
    rows = []
    for category, pattern in CLAIMS.items():
        hits = [f['target'] for f in files if pattern.search(f['target'])]
        rows.append({'category': category, 'status': 'present-by-file-name' if hits else 'not-detected',
                     'evidence': hits[:10], 'basis': 'file-name-pattern', 'confirmed_behaviour': False})
    return rows


def tls_overlap(files: list[dict]) -> list[str]:
    return [f['target'] for f in files if f['target'].replace('/', '\\').rsplit('\\', 1)[-1].lower() in TLS_OVERLAP]


def version_check(package_version, claim: str) -> dict:
    found = '.'.join(str(x) for x in (package_version or []))
    match = re.search(r'(\d+)\.(\d+)', claim)
    if not found:
        return {'package': None, 'author_claim': claim, 'status': 'unreadable'}
    if match and found.split('.')[:2] == [str(int(match.group(1))), str(int(match.group(2)))]:
        return {'package': found, 'author_claim': claim, 'status': 'matches-author-claim'}
    return {'package': found, 'author_claim': claim, 'status': 'differs-from-author-claim'}


class RebornWizard:
    def __init__(self, service):
        self.service = service
        self.data = load()
        self.card = self.data['card']
        service.scenarios[SCENARIO] = self._plan_scenario
        service.safety.gates[SCENARIO] = self._gate

    # ---- stored state (manual observations are bound to the connection) ------------------------------
    def _saved(self, facts):
        return self.service._load('observations', facts['key']) if facts['key'] else {}

    def _pin(self):
        path = self.service.root / 'reborn-pin.json'
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def _artifact(self, digest):
        return self.service.safety.artifact(digest) if digest else None

    # ---- variant gate ----------------------------------------------------------------------------------
    def variant(self, facts) -> dict:
        ident = facts['identity']
        prof = ident['profile']
        rm = facts['observed'].get('rm')
        base = {'profile': prof['id'] if prof else None, 'rm': rm, 'regional': rm in REGIONAL}
        if not prof or ident['basis'] != 'observed':
            return {**base, 'status': 'blocked', 'code': 'model-not-read-from-device',
                    'reason': message('The model must be read from the device; manual input cannot unlock this kit.',
                                      'Модель должна быть прочитана с устройства; ручной ввод не открывает этот набор.')}
        if prof['id'] == 'nokia-n95-family' or not prof.get('variant_known', True) or ident['rm_mismatch']:
            return {**base, 'status': 'blocked', 'code': 'variant-unknown-or-conflicting',
                    'reason': message('The N95 variant is unknown or model and RM disagree.', 'Модификация N95 неизвестна или модель и RM не совпадают.')}
        if prof['id'] == 'nokia-n95-8gb':
            evidence = [e for e in self.data['support_evidence'] if e.get('profile') == 'nokia-n95-8gb'
                        and e.get('firmware') == facts['observed'].get('firmware')]
            if not evidence:
                return {**base, 'status': 'blocked', 'code': 'n95-8gb-unproven',
                        'reason': message('N95 8GB (RM-320 family) has no proven support for this kit; it is not assumed to match the N95.',
                                          'Для N95 8GB (семейство RM-320) поддержка этого набора не доказана; совместимость с N95 не предполагается.')}
        if prof['id'] != 'nokia-n95' and prof['id'] != 'nokia-n95-8gb':
            return {**base, 'status': 'blocked', 'code': 'not-an-n95',
                    'reason': message('This kit targets the Nokia N95 only.', 'Набор предназначен только для Nokia N95.')}
        if not rm:
            return {**base, 'status': 'blocked', 'code': 'rm-not-reported',
                    'reason': message('The device did not report its RM code, so the variant cannot be confirmed.',
                                      'Устройство не сообщило код RM, модификацию подтвердить нельзя.')}
        return {**base, 'status': 'candidate', 'code': 'unverified-candidate',
                'reason': message('Stated target is "Nokia N95 (S60v3 FP1)"; the author names no RM codes or firmware versions. This is a candidate, not a verified match.',
                                  'Заявленная цель — «Nokia N95 (S60v3 FP1)»; автор не называет коды RM и версии прошивки. Это кандидат, а не подтверждённое совпадение.')}

    # ---- gate used by the Safety Net on every apply ------------------------------------------------------
    def _gate(self, row, facts, plan):
        unmet = []
        ev = C.evaluate(dict(facts, required_free=plan['dry_run']['bytes'] * 2 + 1), 'reborn-n95')
        for c in ('connection', 'identity', 'platform', 'firmware', 'files', 'transfer', 'storage'):
            if ev[c]['status'] != 'ready':
                unmet.append({'code': 'gate-' + c, 'text': ev[c]['reason']})
        v = self.variant(facts)
        if v['status'] == 'blocked':
            unmet.append({'code': 'gate-' + v['code'], 'text': v['reason']})
        if ev['rights']['status'] != 'ready':
            unmet.append({'code': 'gate-rights', 'text': message(
                'Device-level installation rights (the installserver.exe patch) are not confirmed. This is only your own observation; it cannot be read by SymPort.',
                'Права установки уровня устройства (патч installserver.exe) не подтверждены. Это только ваше наблюдение, SymPort не может его прочитать.')})
        if not self._saved(facts).get('data_backup'):
            unmet.append({'code': 'gate-no-backup', 'text': message(
                'Confirm that you made your own copy of the data you care about (Backups page or Nokia Suite).',
                'Подтвердите, что вы сделали собственную копию важных данных (страница «Резервные копии» или Nokia Suite).')})
        pin = self._pin()
        item = plan['items'][0] if plan['items'] else None
        if not pin or not item or item['sha256'] != pin['sha256']:
            unmet.append({'code': 'gate-hash-differs-from-pin', 'text': message(
                'The file is not the one you pinned. Import and pin it again.', 'Файл не совпадает с закреплённым. Импортируйте и закрепите его заново.')})
        return unmet

    # ---- actions -----------------------------------------------------------------------------------------
    def state(self, data):
        row, rows, facts = self.service._context(data)
        saved = self._saved(facts)
        pin = self._pin()
        artifact = self._artifact(pin['sha256']) if pin else None
        ev = C.evaluate(facts, 'reborn-n95')
        v = self.variant(facts)
        steps = [
            {'id': 'preflight', 'status': C.worst([ev[c]['status'] for c in ('connection', 'identity', 'platform', 'firmware', 'storage')]
                                                   + [{'blocked': 'unsupported', 'candidate': 'ready'}[v['status']]])},
            {'id': 'rights', 'status': ev['rights']['status']},
            {'id': 'import', 'status': 'ready' if artifact else 'needs-action'},
            {'id': 'backup', 'status': 'ready' if saved.get('data_backup') else 'needs-action'},
        ]
        backups = self._backups()
        return {'card': self.card, 'device': (row or {}).get('id'),
                'reason': None if row else ('no-connection' if not rows else 'device-not-selected'),
                'variant': v, 'checks': [ev[c] for c in ('connection', 'identity', 'platform', 'firmware', 'storage', 'files', 'transfer', 'rights')],
                'pin': pin, 'artifact_present': artifact is not None, 'steps': steps, 'backups': backups,
                'data_backup': saved.get('data_backup'), 'stages': saved.get('reborn_stages', {}),
                'postchecks': {k: v for k, v in saved.get('reborn_stages', {}).items() if k in POSTCHECKS},
                'postcheck_items': list(POSTCHECKS), 'tls_state': self._tls_state(facts),
                'statement': 'SymPort never installs this kit. Success is only an installation you confirm on the phone.'}

    def _backups(self):
        try:
            from symport.phone.backups import BackupStore, default_root
            rows = BackupStore(default_root(self.service.root.parents[2])).list()
        except Exception:  # noqa: BLE001 - informational only
            rows = []
        return {'count': len(rows), 'latest': rows[0]['created'] if rows else None,
                'note': 'SymPort file backups are not tied to a specific phone; they are shown for reference only.'}

    def import_file(self, data):
        try:
            raw = base64.b64decode(data.get('content', ''), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('broken-package: content is not valid base64') from exc
        if not raw or len(raw) > MAX_PACKAGE:
            raise ValueError('broken-package: empty or larger than 32 MiB')
        name = str(data.get('name') or '')[:120]
        try:
            validation = validate_package(name if name.lower().endswith(('.sis', '.sisx')) else 'package.sis', raw)
            info = inspect(raw)
        except (ValueError, KeyError) as exc:
            raise ValueError('broken-package: not a valid SIS 9.x package (' + str(exc)[:120] + ')') from exc
        row, _rows, facts = self.service._context(data)
        target = {'model': facts['observed'].get('model') or '', 'rm': facts['observed'].get('rm') or '',
                  'firmware': facts['observed'].get('firmware') or ''}
        analysis = analyze_package(raw, name=name or 'package.sis', target=target)
        files = components(raw)
        digest = self.service.safety.put_artifact(raw)
        pin = self._pin()
        return {
            'sha256': digest, 'size': len(raw), 'name': name,
            'expected_name': self.card['expected_name'], 'name_matches': name == self.card['expected_name'],
            'package': info['package'], 'signature': inspect_signatures(raw)['status'], 'structure': validation['checksums'],
            'platform_verdict': analysis['platform_verdict'], 'issues': analysis['issues'],
            'capabilities': analysis['capabilities'], 'restricted_capabilities': analysis['restricted_capabilities'],
            'dependencies': analysis['declared'], 'files': files,
            'high_risk_count': sum(f['high_risk'] for f in files),
            'modifications': modifications(files),
            'tls_overlap': tls_overlap(files), 'tls_state': self._tls_state(facts),
            'version_check': version_check(info['package'].get('version'), self.card['version']),
            'pinned': bool(pin and pin['sha256'] == digest), 'differs_from_pin': bool(pin and pin['sha256'] != digest),
            'known_author_hash': None,
            'statement': 'Static analysis only. The author publishes no hash; confirm the file source yourself, then pin it.',
        }

    def _tls_state(self, facts) -> dict:
        tls = self._saved(facts).get('tls', {})
        return {k: tls.get(k, {}).get('state', 'unknown') for k in ('mbedtls-lib', 'ssl-patch')}

    def pin(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that you obtained this file from the author')
        digest = data.get('sha256')
        raw = self._artifact(digest)
        if raw is None:
            raise ValueError('Import the file first')
        value = {'sha256': digest, 'size': len(raw), 'name': str(data.get('name') or '')[:120], 'pinned_at': now(),
                 'source': 'user-confirmed', 'author_hash': None}
        from symport.catalog.service import save
        save(self.service.root / 'reborn-pin.json', value)
        return value

    def attest(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm your statement')
        row, facts = self.service._need_device(data)
        saved = self._saved(facts)
        saved['data_backup'] = {'at': now(), 'source': 'manual',
                                'note': 'The user states a separate copy of important data exists; SymPort did not verify it.'}
        self.service._save('observations', facts['key'], saved)
        return {'data_backup': saved['data_backup']}

    def stage(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that this is what you observed on the phone')
        stage, result = data.get('stage'), data.get('result')
        if stage not in STAGES + POSTCHECKS or result not in STAGE_RESULTS:
            raise ValueError('Invalid stage observation')
        row, facts = self.service._need_device(data)
        saved = self._saved(facts)
        saved.setdefault('reborn_stages', {})[stage] = {'result': result, 'at': now(), 'source': 'manual', 'evidence': 'user-reported',
                                                        'note': str(data.get('note') or '')[:200]}
        self.service._save('observations', facts['key'], saved)
        return {'stages': saved['reborn_stages'], 'success': self.outcome(saved['reborn_stages'])}

    @staticmethod
    def outcome(stages) -> str:
        """Only a user-confirmed installation counts; a copy never does."""
        if stages.get('installed', {}).get('result') == 'fail':
            return 'failed-reported'
        if stages.get('installed', {}).get('result') == 'pass':
            return 'installed-reported' if stages.get('network-works', {}).get('result') == 'pass' else 'installed-reported-unchecked'
        return 'not-confirmed'

    # ---- Safety Net scenario -----------------------------------------------------------------------------
    def _plan_scenario(self, row, facts, data):
        pin = self._pin()
        digest = data.get('sha256')
        if not pin:
            raise ValueError('Import and pin the file first')
        if digest != pin['sha256']:
            raise ValueError('hash-differs-from-pin: this file is not the pinned one')
        raw = self._artifact(digest)
        if raw is None:
            raise ValueError('The pinned file is missing; import it again')
        files = components(raw)
        high = [f for f in files if f['high_risk']]
        blocking = [
            {'code': 'alpha-software', 'satisfied_by': 'acknowledgement', 'text': message(
                'Alpha release by a single author. You accept the risk of data loss and a phone that needs reformatting.',
                'Альфа-версия одного автора. Вы принимаете риск потери данных и необходимости форматировать телефон.')},
            {'code': 'irreversible-no-uninstall', 'satisfied_by': 'acknowledgement', 'text': message(
                'No uninstall procedure exists. The author\'s only recovery is formatting the phone (erases user data). SymPort cannot undo the installation.',
                'Процедуры удаления нет. Единственное восстановление у автора — форматирование телефона (стирает данные). SymPort не может откатить установку.')},
            {'code': 'variant-not-stated-by-author', 'satisfied_by': 'acknowledgement', 'text': message(
                'The author does not name compatible RM codes or firmware versions. Your phone is an unverified candidate.',
                'Автор не называет совместимые коды RM и версии прошивки. Ваш телефон — непроверенный кандидат.')},
        ]
        if facts['observed'].get('rm') in REGIONAL:
            blocking.append({'code': 'regional-variant', 'satisfied_by': 'acknowledgement', 'text': message(
                'RM-160 (NAM) / RM-245 (China) are not automatically compatible.', 'RM-160 (NAM) / RM-245 (Китай) автоматически не считаются совместимыми.')})
        overlap = tls_overlap(files)
        if overlap:
            tls = self._tls_state(facts)
            blocking.append({'code': 'tls-stack-overlap', 'satisfied_by': 'acknowledgement', 'text': message(
                'The package contains ' + ', '.join(overlap) + ', which the separate TLS stack also owns. TLS component state on this phone: '
                + ', '.join(f'{k}={v}' for k, v in tls.items()) + '. Installing both can replace one with the other.',
                'Пакет содержит ' + ', '.join(overlap) + ', которыми владеет и отдельный TLS-стек. Состояние TLS-компонентов на этом телефоне: '
                + ', '.join(f'{k}={v}' for k, v in tls.items()) + '. Установка обоих может заменить один другим.')})
        if high:
            blocking.append({'code': 'high-risk-components', 'satisfied_by': 'acknowledgement', 'text': message(
                f'The package contains {len(high)} system-level components (executables, resources, system or private paths).',
                f'Пакет содержит системных компонентов: {len(high)} (исполняемые файлы, ресурсы, системные или приватные пути).')})
        name = self.card['expected_name']
        phone_actions = [{
            'component': 'reborn-hybrid-cfw',
            'steps': [message('Make sure the installserver.exe patch is active (your own check).', 'Убедитесь, что патч installserver.exe активен (ваша проверка).'),
                      message('Prefer a clean installation (author).', 'По возможности чистая установка (рекомендация автора).'),
                      message('Open SymPort-Reborn/' + name + ' in the phone file manager and install it; follow the installer prompts.',
                              'Откройте SymPort-Reborn/' + name + ' в файловом менеджере телефона и установите; следуйте запросам установщика.'),
                      message('Restart the phone as the installer instructs, then check the network and basic functions.',
                              'Перезагрузите телефон, как требует установщик, затем проверьте сеть и основные функции.'),
                      message('Record each stage in the wizard.', 'Отметьте каждый этап в мастере.')],
            'restore': message('No uninstall exists. Author: format the device (erases user data). SymPort can remove only the copied SIS from the card.',
                               'Удаления нет. Автор: форматирование телефона (стирает данные). SymPort может удалить только скопированный SIS с карты.'),
        }]
        return self.service.safety.build_plan(
            row, facts, scenario=SCENARIO, label='Reborn Hybrid CFW alpha (N95)', folder=FOLDER,
            items=[{'name': name, 'sha256': digest, 'size': len(raw), 'component': 'reborn-hybrid-cfw'}],
            risk={'level': 'high', 'blocking': blocking, 'irreversible': True},
            restore={'kind': 'files-created-by-symport', 'system_restore': 'unsupported', 'author_recovery': 'format-device',
                     'note': 'Rollback removes the copied SIS only; installed software and system changes are not restored.'},
            phone_actions=phone_actions,
            extra={'high_risk_components': [f['target'] for f in high], 'modifications': modifications(files),
                   'version_check': version_check(inspect(raw)['package'].get('version'), self.card['version'])})
