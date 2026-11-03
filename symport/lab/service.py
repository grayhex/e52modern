"""SymPort orchestration/reports over the MGO agent; firmware stays in MGO storage."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import secrets
import struct
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from symport.catalog.packages import validate_package
from symport.catalog.service import save

from .client import AgentError, MgoClient

STATES = {'installed', 'launched', 'failed', 'unsupported', 'not-tested'}
KEYS = {'up', 'down', 'left', 'right', 'ok', 'lsk', 'rsk', 'clear', 'star', 'hash', 'call', 'end', 'applications', *'0123456789'}
HEX = re.compile(r'^[a-f0-9]{32}$')
CODE = re.compile(r'^[A-Za-z0-9._-]{1,32}$')
LIMIT = 2 * 1024**3


def now():
    return datetime.now(UTC).isoformat()


class HashedStream:
    def __init__(self, stream):
        self.stream, self.digest = stream, hashlib.sha256()

    def read(self, size):
        data = self.stream.read(size)
        self.digest.update(data)
        return data


class EmulatorLab:
    def __init__(self, repo: Path, resolver, devices, agent=None):
        self.root = repo / 'build/symport/emulator-lab'
        self.resolver, self.devices, self.agent = resolver, devices, agent or MgoClient()
        self.lock = threading.RLock()
        self.input_lock = threading.Lock()
        self.active = None
        self.current = None
        self.firmware = None
        self.generation = 0
        self.uploads = json.loads((self.root / 'uploads.json').read_text(encoding="utf-8")) if (self.root / 'uploads.json').exists() else {}
        for path in (self.root / 'reports').glob('*.json'):
            report = json.loads(path.read_text(encoding="utf-8"))
            if report.get('running'):
                report.update(running=False, status='not-tested', error='SymPort restarted; inspect MGO state before retry')
                save(path, report)

    def _record(self, report):
        with self.lock:
            report['updated'] = now()
            save(self.root / 'reports' / (report['id'] + '.json'), report)

    def _new(self, kind, package=None):
        report = {'schema': 'symport.emulator-lab/1', 'id': secrets.token_hex(16), 'kind': kind, 'engine': 'EKA2L1 via MGO',
                  'status': 'not-tested', 'install': 'not-tested', 'launch': 'not-tested',
                  'physical_device': 'not-tested', 'package': package, 'firmware': self.firmware,
                  'created': now(), 'running': True, 'screenshots': [], 'events': [],
                  'limitations': ['Эмулятор не подтверждает работу на физической E52.',
                                  'Поддержка прошивки и системных служб зависит от EKA2L1.']}
        self._record(report)
        return report

    def state(self):
        reports = sorted([json.loads(p.read_text(encoding="utf-8")) for p in (self.root / 'reports').glob('*.json')], key=lambda r: r['created'], reverse=True)[:50]
        try:
            health = self.agent.request('GET', '/agent/health')
            result = {'available': True, 'health': health}
            if health.get('instance', {}).get('running'):
                try:
                    result['session'] = self.agent.request('GET', '/v1/session')
                    result['keys'] = self.agent.request('GET', '/v1/keys')
                    result['capabilities'] = self.agent.request('GET', '/v1/capabilities')
                    if result['session'].get('state') in ('crashed', 'launch_failed') and self.current:
                        report = self.report(self.current)
                        if report.get('launch') == 'launched':
                            report.update(status='failed', launch='failed', runtime_failure=result['session'])
                            self._record(report)
                except AgentError as exc:
                    result['control_reason'] = str(exc)
        except AgentError as exc:
            result = {'available': False, 'status': 'unsupported' if exc.code == 'disabled' else 'not-tested', 'reason': str(exc)}
        summaries = [{k: r[k] for k in ('id', 'kind', 'status', 'install', 'launch', 'running', 'created', 'updated', 'state', 'package') if k in r} for r in reports]
        return dict(result, reports=summaries, uploads=self.uploads, active=self.active, current=self.current,
                    java={'status': 'unsupported', 'engine': 'KEmulator (separate MGO core)',
                          'reason': 'MGO EKA2L1 agent не устанавливает JAR/JAD. KEmulator не является Symbian Java ME.'})

    def upload_firmware(self, stream, length, slot, name, bundle=None):
        if slot not in ('rom', 'rpkg', 'archive', 'vpl', 'fpsx') or not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,119}', name) or '..' in name:
            raise ValueError('Сохраните исходное безопасное имя файла прошивки')
        if not 0 < length <= LIMIT or (slot == 'vpl' and length > 4 * 1024 * 1024):
            raise ValueError('Firmware exceeds upload limit')
        if slot in ('vpl', 'fpsx') and not HEX.fullmatch(bundle or ''):
            raise ValueError('VPL/FPSX requires a fresh bundle ID')
        stream = HashedStream(stream)
        agent_name = name if slot in ('vpl', 'fpsx') else secrets.token_hex(6) + '-' + name[-100:]
        uploaded = self.agent.upload('/agent/firmware/' + slot, agent_name, stream, length, bundle)
        entry = {'id': secrets.token_hex(16), 'slot': slot, 'name': name, 'size': length,
                 'sha256': stream.digest.hexdigest(), 'agent_file': uploaded['file'], 'bundle': bundle,
                 'created': now()}
        with self.lock:
            self.uploads[entry['id']] = entry
            save(self.root / 'uploads.json', self.uploads)
        return entry

    def report(self, key):
        if not isinstance(key, str) or not HEX.fullmatch(key):
            raise ValueError('Invalid test report ID')
        return json.loads((self.root / 'reports' / (key + '.json')).read_text(encoding="utf-8"))

    def frame(self):
        raw = self.agent.request('GET', '/v1/screenshot?region=guest', binary=True, timeout=5)
        if len(raw) < 24 or raw[:8] != b'\x89PNG\r\n\x1a\n':
            raise AgentError('Invalid guest screenshot', code='invalid-screen')
        width, height = struct.unpack('>II', raw[16:24])
        return {'png': base64.b64encode(raw).decode(), 'width': width, 'height': height}

    def _capture(self, report):
        frame = self.frame()
        raw = base64.b64decode(frame['png'])
        name = report['id'] + '-' + secrets.token_hex(4) + '.png'
        directory = self.root / 'screenshots'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        (directory / name).write_bytes(raw)
        report['screenshots'].append({'name': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                                      'width': frame['width'], 'height': frame['height'], 'at': now()})
        self._record(report)
        return frame

    def execute(self, data):
        action = data.get('action')
        if action == 'state':
            return self.state()
        if action == 'bundle':
            return {'bundle': secrets.token_hex(16)}
        if action == 'report':
            return self.report(data.get('id'))
        if action == 'frame':
            return self.frame()
        if action == 'logs':
            return self.agent.request('GET', '/agent/log')
        if action in ('shot', 'observe'):
            report = self.report(data.get('id') or self.current)
            if report['id'] != self.current or report.get('running') or not any(e['stage'] == 'firmware-booted' for e in report['events']):
                raise ValueError('Снимок доступен для завершённого теста текущего сеанса')
            if action == 'observe':
                if data.get('step') not in ('applied', 'home', 'menu', 'lists', 'dialogs') or data.get('result') not in ('pass', 'fail', 'not-tested', 'unsupported'):
                    raise ValueError('Unknown manual observation')
                if report['kind'] != 'theme' or report['install'] != 'installed':
                    raise ValueError('Сначала установите тему')
                report.setdefault('observations', []).append({'step': data['step'], 'result': data['result'], 'at': now(), 'source': 'user-observation'})
                self._record(report)
            try:
                frame = self._capture(report)
            except AgentError as exc:
                if action != 'observe':
                    raise
                report['screen_reason'] = str(exc)
                self._record(report)
                return {'status': 'unsupported', 'reason': str(exc)}
            report['logs'] = self.agent.request('GET', '/agent/log')
            self._record(report)
            return frame
        if action == 'saved-shot':
            report = self.report(data.get('id'))
            shot = next((s for s in report['screenshots'] if s['name'] == data.get('name')), None)
            if not shot:
                raise ValueError('Screenshot not found in this report')
            return {'png': base64.b64encode((self.root / 'screenshots' / shot['name']).read_bytes()).decode()}
        if action == 'key':
            if data.get('key') not in KEYS or data.get('event') not in ('down', 'up'):
                raise ValueError('Unknown hardware key')
            with self.input_lock:
                return self.agent.request('POST', '/v1/input/key', {'key': data['key'], 'action': data['event']})
        if action == 'release':
            with self.input_lock:
                return self.agent.request('POST', '/v1/input/release', {})
        if action == 'stop':
            if self.active and self.report(self.active)['kind'] == 'firmware':
                raise ValueError('Дождитесь завершения установки прошивки')
            self.generation += 1
            self.agent.request('DELETE', '/agent/instance', timeout=30)
            return {'status': 'not-tested', 'state': 'stopped'}
        if action == 'select':
            code = data.get('code')
            if not isinstance(code, str) or not CODE.fullmatch(code):
                raise ValueError('Choose an installed firmware')
            return self.agent.request('PUT', '/agent/defaults', {'platform': 'symbian', 'code': code})
        if action == 'transfer':
            report = self.report(data.get('id'))
            if report['kind'] not in ('app', 'theme') or report['install'] != 'installed':
                raise ValueError('Сначала необходим подтверждённый результат установки в эмуляторе')
            if data.get('confirm') is not True:
                raise ValueError('Подтвердите передачу на физический телефон')
            raw = (self.root / 'packages' / (report['id'] + '.bin')).read_bytes()
            if hashlib.sha256(raw).hexdigest() != report['package']['sha256']:
                raise ValueError('Tested package integrity changed')
            result = self.devices.execute({'action': 'software-transfer', 'device': data.get('device'),
                                           'path': data.get('path'), 'confirm': True,
                                           'content': base64.b64encode(raw).decode()})
            report['physical_transfer'] = {'at': now(), 'result': result, 'installation': 'not-tested'}
            self._record(report)
            return result
        if action in ('start', 'reboot', 'test', 'install-firmware'):
            with self.lock:
                if self.active:
                    raise ValueError('Дождитесь текущей операции Emulator Lab')
                if action in ('test', 'install-firmware') and data.get('confirm') is not True:
                    raise ValueError('Подтвердите установку пакета или пользовательской прошивки')
                report = self._new('firmware' if action == 'install-firmware' else 'session')
                self.active = self.current = report['id']
                generation = self.generation
                threading.Thread(target=self._run, args=(report, data, generation), daemon=True).start()
            return report
        raise ValueError('Unknown Emulator Lab operation')

    def _run(self, report, data, generation):
        phase = 'session'
        def event(stage, evidence=None):
            if generation != self.generation:
                raise AgentError('Session stopped while operation was running', code='session-stopped')
            report['events'].append({'stage': stage, 'at': now(), 'evidence': evidence})
            self._record(report)
        try:
            action = data['action']
            if action == 'install-firmware':
                phase = 'firmware'
                ids = data.get('uploads')
                if not isinstance(ids, list) or not 1 <= len(ids) <= 128:
                    raise ValueError('Choose uploaded firmware files')
                entries = [self.uploads[i] for i in ids if isinstance(i, str) and i in self.uploads]
                if any(e.get('consumed') for e in entries):
                    raise ValueError('MGO уже использовал этот комплект. Загрузите файлы заново.')
                if len(entries) != len(ids):
                    raise ValueError('Unknown firmware upload')
                slots = {e['slot']: e for e in entries if e['slot'] != 'fpsx'}
                if len(slots) != sum(e['slot'] != 'fpsx' for e in entries):
                    raise ValueError('Choose only one file for each firmware slot')
                if 'vpl' not in slots and any(e['slot'] == 'fpsx' for e in entries):
                    raise ValueError('FPSX is supported only with its original VPL manifest')
                if ('rpkg' in slots and 'rom' not in slots) or len([s for s in ('rom', 'archive', 'vpl') if s in slots]) != 1:
                    raise ValueError('Choose ROM (+RPKG), archive, or VPL + FPSX')
                body = {slot: e['agent_file'] for slot, e in slots.items()}
                if 'vpl' in slots:
                    bundles = {e['bundle'] for e in entries}
                    if len(bundles) != 1 or None in bundles:
                        raise ValueError('VPL/FPSX must belong to one original bundle')
                    body['bundle'] = slots['vpl']['bundle']
                    if data.get('variant') is not None:
                        variant = data['variant']
                        if not isinstance(variant, int) or not 0 <= variant <= 65535:
                            raise ValueError('Variant must be a zero-based integer')
                        body['variant'] = variant
                report['firmware_inputs'] = entries
                job = self.agent.request('POST', '/agent/firmware/install', body)
                event('firmware-install-requested', job)
                with self.lock:
                    for entry in entries:
                        entry['consumed'] = True
                    save(self.root / 'uploads.json', self.uploads)
                deadline = time.monotonic() + 3500
                while job['state'] == 'running' and time.monotonic() < deadline:
                    time.sleep(1)
                    job = self.agent.request('GET', '/agent/jobs/' + quote(job['id'], safe=''))
                    report['agent_job'] = job
                    self._record(report)
                if job['state'] != 'succeeded':
                    raise AgentError(job.get('error') or 'Firmware installation incomplete', code='firmware-install-failed')
                report.update(status='installed', install='installed', firmware=self.agent.request('GET', '/agent/health')['firmware'])
                event('firmware-installed', job)
                return
            package = None
            if action == 'test':
                phase = 'prepare'
                name, raw, hint = self.resolver(data)
                package = {'name': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'source': data.get('source'), 'reference': data.get('reference')}
                report['package'] = package
                if Path(name).suffix.lower() in ('.jar', '.jad'):
                    report.update(status='unsupported', install='unsupported', launch='unsupported', engine='not-run',
                                  alternative_engine='KEmulator (separate MGO core)',
                                  error='JAR/JAD не проверяются этим EKA2L1 agent. KEmulator не является Symbian Java ME.')
                    return
                validate_package(name, raw)
                from symport.sis.reader import inspect
                info = inspect(raw)
                theme = hint == 'theme' or data.get('kind') == 'theme' or (any('\\skins\\' in f['target'].lower() for f in info['files']) and not any(f['target'].lower().endswith('.exe') for f in info['files']))
                report['kind'] = 'theme' if theme else 'app'
                folder = self.root / 'packages'
                folder.mkdir(parents=True, exist_ok=True, mode=0o700)
                (folder / (report['id'] + '.bin')).write_bytes(raw)
            health = self.agent.request('GET', '/agent/health')
            devices = health.get('firmware', {}).get('devices', [])
            code = data.get('code') or health.get('defaults', {}).get('symbian')
            selected = next((d for d in devices if d['code'] == code), None)
            if not selected:
                raise AgentError('Выберите установленную пользовательскую прошивку', code='no-firmware')
            report['emulator'] = health.get('emulator', 'unknown')
            self.firmware = report['firmware'] = selected
            event('starting-session', selected)
            save_key = hashlib.sha256(('symport-lab:' + code).encode()).hexdigest()[:32]
            if action == 'reboot' or not health.get('instance', {}).get('running') or health['instance'].get('saveKey') != save_key:
                if health.get('instance', {}).get('running'):
                    self.agent.request('DELETE', '/agent/instance', timeout=30)
                self.agent.request('POST', '/agent/instance', {'saveKey': save_key}, timeout=90)
            deadline = time.monotonic() + 90
            while True:
                try:
                    self.agent.request('GET', '/v1/status', timeout=5)
                    break
                except AgentError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.5)
            current_device = self.agent.request('GET', '/v1/devices').get('current') or {}
            if current_device.get('code') != code:
                self.agent.request('POST', '/v1/devices/' + quote(code, safe='') + '/boot', {}, timeout=300)
            self.agent.request('PUT', '/agent/defaults', {'platform': 'symbian', 'code': code})
            event('firmware-booted')
            if action != 'test':
                report['state'] = 'running'
                return
            phase = 'install'
            before = self.agent.request('GET', '/v1/apps').get('apps', [])
            uploaded = self.agent.upload('/agent/upload/package', package['name'], io.BytesIO(raw), len(raw))
            installed = self.agent.request('POST', '/v1/apps', {'path': uploaded['path'], 'type': 'sis'}, timeout=600)
            report.update(install='installed', status='installed', install_evidence=installed)
            event('installed', installed)
            if report['kind'] == 'theme':
                report['launch'] = 'unsupported'
                report['limitations'].append('Применение темы, системное меню и shell этой прошивки требуют ручной проверки; EKA2L1 может их не поддерживать.')
                report['instructions'] = 'Откройте Меню → Средства/Параметры → Темы → Общие. Примените тему вручную, проверьте меню, списки и диалоги. UID темы не запускается.'
                return
            added = installed.get('added') or []
            after = self.agent.request('GET', '/v1/apps').get('apps', [])
            before_ids = {str(a['uid']).lower() for a in before}
            candidates = added or [a for a in after if str(a['uid']).lower() not in before_ids]
            if not candidates:
                # Exact registry match is evidence for reinstall; never assume a package UID is an executable UID.
                candidates = [a for a in after if str(a['uid']).lower() == hex(info['uid3']).lower()]
            report['applications'] = candidates
            if len(candidates) != 1 or not re.fullmatch(r'(0x)?[0-9a-fA-F]{1,8}', str(candidates[0].get('uid', ''))):
                report['launch_reason'] = 'Установка завершена, но нельзя однозначно определить приложение. Запустите его из меню телефона.'
                return
            phase = 'launch'
            uid = str(candidates[0]['uid'])
            launched = self.agent.request('POST', '/v1/apps/' + uid + '/launch', {'wait': True, 'timeoutMs': 60000}, timeout=75)
            report['launch_evidence'] = launched
            if launched.get('state') != 'running':
                if launched.get('state') in ('failed', 'launch_failed', 'crashed', 'exited'):
                    raise AgentError('EKA2L1 reports ' + launched['state'], code='launch-failed')
                report['launch_reason'] = 'EKA2L1 не подтвердил running; результат запуска не проверен.'
                return
            report.update(launch='launched', status='launched')
            event('launched', launched)
        except (ValueError, OSError, KeyError) as exc:
            report.update(status='failed', error=str(exc)[:500])
            if phase in ('install', 'firmware') and report['install'] != 'installed':
                report['install'] = 'failed'
            if phase == 'launch':
                report['launch'] = 'failed'
        except Exception as exc:
            report.update(status='failed', error='Unexpected Lab failure: ' + type(exc).__name__)
        finally:
            if generation != self.generation:
                # Stop may race a slow start/boot response. No new operation can begin until this worker finishes.
                try:
                    self.agent.request('DELETE', '/agent/instance', timeout=30)
                except AgentError:
                    pass
            if report['status'] != 'unsupported':
                try:
                    report['logs'] = self.agent.request('GET', '/agent/log')
                except (ValueError, OSError) as exc:
                    report['log_error'] = str(exc)
                if generation == self.generation and any(e['stage'] == 'firmware-booted' for e in report['events']):
                    try:
                        self._capture(report)
                    except (ValueError, OSError) as exc:
                        report['screen_reason'] = str(exc)
            report.update(running=False, finished=now())
            self._record(report)
            with self.lock:
                self.active = None
