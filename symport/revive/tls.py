"""Symbian TLS / CA revival (#34): applicability, pinned components, read-only diagnostics, kits.

SymPort never installs or replaces system files. It can (a) tell which TLS stack could serve an
application on a given phone model, according to the component author's documentation,
(b) obtain a *pinned* component (size + SHA-256 must match) or accept a manual import,
(c) copy it to the phone through the existing device boundary with read-back verification and
(d) give step-by-step instructions for what the user does on the phone. "Installed" is only ever
what the user reports; a transferred file is ``transferred-awaiting-install``.
"""
from __future__ import annotations

import base64
import hashlib
import io
import ipaddress
import json
import re
import socket
import ssl
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath

from symport.catalog.download import Redirects, public_https
from symport.catalog.packages import MAX_PACKAGE, validate_package
from symport.catalog.service import now
from symport.phone.registry import registry

from . import checks as C
from .profiles import PLANNING_MARGIN

COMPONENTS_FILE = Path(__file__).with_name('tls_components.json')
HOSTS = frozenset({'nnproject.cc'})
TARGETS = ('nokia-e52', 'nokia-e72', 'nokia-n95', 'nokia-n95-8gb', 'nokia-n97-mini')
# Author documentation (README "Compatibility", nnproject.cc/tls): EKA2 S60 3rd (9.1-9.3) and 5th (9.4).
AUTHOR_SYMBIAN = ('9.1', '9.2', '9.3', '9.4')
SOURCE = 'https://github.com/shinovon/symbian-tls#compatibility'
INSTALL_STATES = ('installed', 'not-installed', 'failed', 'not-tested')
RECORDABLE = ('mbedtls-lib', 'ssl-patch', 'ssl-original-backup', 'https-test')
FOLDER = 'SymPort-TLS'
TEST_HOSTS = ('example.com', 'www.wikipedia.org', 'github.com')
HOST = re.compile(r'^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$')
NO_KEYS = ('.key', '.pem', '.p12', '.pfx')

APP_KINDS = {
    'native-system': {'title': {'en': 'Native app using the system SSL', 'ru': 'Нативное приложение, системный SSL'}, 'stack': 'system-ssl'},
    'native-bundled': {'title': {'en': 'Native app linked against mbedtls.dso', 'ru': 'Нативное приложение с mbedtls.dso'}, 'stack': 'mbedtls-lib'},
    'java': {'title': {'en': 'Java (J2ME) app', 'ru': 'Java-приложение (J2ME)'}, 'stack': 'java-ssl'},
    'qt': {'title': {'en': 'Qt app', 'ru': 'Qt-приложение'}, 'stack': 'qt-ssl'},
}
STACKS = {
    'system-ssl': {
        'title': {'en': 'System SSL (replacement)', 'ru': 'Системный SSL (замена)'},
        'components': ['mbedtls-lib', 'ssl-patch'], 'risk': 'high',
        'note': {'en': 'Replaces C:\\sys\\bin\\ssl.dll. Author: applies to native and J2ME apps. SymPort only transfers the file; extraction is yours, on the phone.',
                 'ru': 'Заменяет C:\\sys\\bin\\ssl.dll. По словам автора: нативные и J2ME-приложения. SymPort только переносит файл; распаковка — ваша, на телефоне.'},
    },
    'mbedtls-lib': {
        'title': {'en': 'MBedTLS library', 'ru': 'Библиотека MBedTLS'},
        'components': ['mbedtls-lib'], 'risk': 'medium',
        'note': {'en': 'For applications built against mbedtls.dso. An app that is not built for it gains nothing.',
                 'ru': 'Для приложений, собранных с mbedtls.dso. Приложению, не собранному под неё, она ничего не даёт.'},
    },
    'java-ssl': {
        'title': {'en': 'Java SSL', 'ru': 'Java SSL'}, 'components': [], 'risk': 'low', 'via': 'system-ssl',
        'note': {'en': 'Covered by the system SSL patch according to the author; the separate Java patch is marked "not used anymore" and is not offered.',
                 'ru': 'По словам автора покрывается патчем системного SSL; отдельный Java-патч помечен «не используется» и не предлагается.'},
    },
    'qt-ssl': {
        'title': {'en': 'Qt SSL', 'ru': 'Qt SSL'}, 'components': [], 'risk': 'low', 'unsupported': True,
        'note': {'en': 'The author states the patch does not apply to Qt. No component is offered.',
                 'ru': 'Автор указывает, что патч не применим к Qt. Компонент не предлагается.'},
    },
}


def load_components() -> dict:
    document = json.loads(COMPONENTS_FILE.read_text(encoding='utf-8'))
    if document.get('schema') != 1:
        raise ValueError('Unsupported TLS component catalog')
    for key, c in document['components'].items():
        if (len(c['sha256']) != 64 or any(ch not in '0123456789abcdef' for ch in c['sha256'])
                or not 0 < c['size'] <= MAX_PACKAGE or Path(c['name']).name != c['name']
                or not c['url'].startswith('https://') or key != re.sub(r'[^a-z0-9-]', '', key)):
            raise ValueError('Invalid TLS component pin: ' + key)
        public_https(c['url'], resolver=lambda *a, **k: [(0, 0, 0, '', ('8.8.8.8', 443))], hosts=HOSTS)
    return document['components']


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_component(spec: dict, raw: bytes) -> dict:
    """Pin first (size + SHA-256), then structure. Anything else is refused."""
    if len(raw) != spec['size'] or sha(raw) != spec['sha256']:
        raise ValueError('hash-mismatch: size or SHA-256 differs from the pinned build')
    suffix = PurePosixPath(spec['name']).suffix.lower()
    if suffix == '.sis':
        info = validate_package(spec['name'], raw)
        from symport.sis.reader import inspect
        uid = f"0x{inspect(raw)['package']['uid']:08x}"
        if uid != spec['package']['uid']:
            raise ValueError('broken-package: package UID differs from the pin')
        return {'format': 'sis', 'package_uid': uid, 'signed': info['signed'], 'signature_verification': 'not-verified',
                'checksums': info['checksums']}
    if suffix == '.zip':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                infos = archive.infolist()
                names = {i.filename for i in infos if not i.is_dir()}
                if len(infos) > 20 or sum(i.file_size for i in infos) > 4 * 1024 * 1024:
                    raise ValueError('broken-package: archive limits exceeded')
                for i in infos:
                    p = PurePosixPath(i.filename)
                    if p.is_absolute() or '..' in p.parts or '\\' in i.filename or p.suffix.lower() in NO_KEYS:
                        raise ValueError('broken-package: unsafe archive entry')
                if names != set(spec['contents']) or archive.testzip() is not None:
                    raise ValueError('broken-package: archive contents differ from the pin')
        except zipfile.BadZipFile as exc:
            raise ValueError('broken-package: not a valid ZIP archive') from exc
        return {'format': 'zip', 'contents': sorted(names)}
    raise ValueError('broken-package: unsupported component format')


def default_probe(host: str, timeout: float = 8.0) -> dict:
    """HTTPS reachability from *this server* with full certificate verification (never disabled)."""
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return {'ok': False, 'error': 'dns'}
    if not answers or any(not ipaddress.ip_address(a[4][0]).is_global for a in answers):
        return {'ok': False, 'error': 'non-public-address'}
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=timeout) as plain, \
                context.wrap_socket(plain, server_hostname=host) as tls:
            cert = tls.getpeercert() or {}
            return {'ok': True, 'tls_version': tls.version(), 'cipher': (tls.cipher() or [None])[0],
                    'leaf': {'subject': _name(cert.get('subject', ())), 'issuer': _name(cert.get('issuer', ())),
                             'not_before': cert.get('notBefore'), 'not_after': cert.get('notAfter')}}
    except ssl.SSLCertVerificationError:
        return {'ok': False, 'error': 'certificate-verify-failed'}
    except ssl.SSLError:
        return {'ok': False, 'error': 'tls-error'}
    except TimeoutError:
        return {'ok': False, 'error': 'timeout'}
    except OSError:
        return {'ok': False, 'error': 'offline'}


def _name(rdn) -> str:
    return ', '.join(f'{k}={v}' for part in rdn for k, v in part)


def _cert_time(value):
    try:
        return datetime.strptime(value, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


class TlsRevival:
    def __init__(self, service):
        self.service = service
        self.cache = service.root / 'tls'
        self.components = load_components()
        self.probe = default_probe
        self.opener = urllib.request.build_opener(_Redirects())

    def register_safety(self):
        """Copying TLS components goes through the Recovery Safety Net (plan → snapshot → apply)."""
        self.service.scenarios['tls'] = self._plan_scenario
        self.service.safety.gates['tls'] = self._gate

    @staticmethod
    def _gate(row, facts, plan):
        ev = C.evaluate(facts, 'network-certs')
        return [{'code': 'gate-' + c, 'text': ev[c]['reason']} for c in ('connection', 'identity', 'platform')
                if ev[c]['status'] != 'ready']

    def _plan_scenario(self, row, facts, data):
        keys = data.get('components')
        if not isinstance(keys, list) or not keys or len(keys) > 4:
            raise ValueError('Choose components')
        order = []
        for k in keys:
            for dep in [*self._spec(k)['depends_on'], k]:
                if dep not in order:
                    order.append(dep)
        items, blocking, level = [], [], 'low'
        for k in order:
            spec = self.components[k]
            raw = self._cached(spec)
            if raw is None:
                raise ValueError(f'Obtain the pinned file for {k} first (download or import)')
            self.service.safety.put_artifact(raw)
            items.append({'name': spec['name'], 'sha256': spec['sha256'], 'size': spec['size'], 'component': k})
            if spec['risk'] == 'high':
                level = 'high'
                blocking.append({'code': 'manual-system-replacement', 'satisfied_by': 'acknowledgement',
                                 'text': {'en': 'Extracting ssl.zip into C:\\sys\\bin is a manual system change SymPort cannot undo. Keep your own copy of the original ssl.dll.',
                                          'ru': 'Распаковка ssl.zip в C:\\sys\\bin — ручное системное изменение, которое SymPort не откатывает. Сохраните свою копию оригинального ssl.dll.'}})
            elif level == 'low':
                level = 'medium'
        guide = [{'component': k, 'steps': self._guide(k), 'restore': self._restore(k)} for k in order]
        return self.service.safety.build_plan(
            row, facts, scenario='tls', label='Symbian TLS components', folder=FOLDER, items=items,
            risk={'level': level, 'blocking': blocking, 'irreversible': level == 'high'},
            restore={'kind': 'files-created-by-symport', 'system_restore': 'unsupported',
                     'note': 'Rollback removes the copied archives only; installed software and replaced system files are restored by you.'},
            phone_actions=guide)

    # ---- helpers ---------------------------------------------------------------------------------
    def _path(self, spec):
        return self.cache / spec['sha256'] / spec['name']

    def _cached(self, spec) -> bytes | None:
        path = self._path(spec)
        try:
            if path.is_file() and not path.is_symlink():
                raw = path.read_bytes()
                if len(raw) == spec['size'] and sha(raw) == spec['sha256']:
                    return raw
        except OSError:
            pass
        return None

    def _spec(self, key):
        if not isinstance(key, str) or key not in self.components:
            raise ValueError('Unknown TLS component')
        return self.components[key]

    def applicability(self) -> list[dict]:
        out = []
        reg = registry()
        for tid in TARGETS:
            p = reg.get(tid)
            if not p:
                continue
            supported = p.get('symbian') in AUTHOR_SYMBIAN
            row = {'target': tid, 'name': p['name'], 's60': p['s60'], 'symbian': p.get('symbian'), 'stacks': {}}
            for sid, stack in STACKS.items():
                if stack.get('unsupported'):
                    status = 'not-applicable'
                elif not supported:
                    status = 'unknown'
                else:
                    status = 'documented'
                row['stacks'][sid] = {
                    'status': status, 'tested': 'not-tested', 'basis': 'author-documentation' if status == 'documented' else 'none',
                    'source': SOURCE,
                    'abi': 'ARMv5 / EKA2 (author build for 9.1+)' if status == 'documented' else None,
                    'firmware': 'The author does not state firmware versions; exact firmware is not verified',
                    'capabilities': 'SIS is unsigned: needs the InstallServer patch; extraction to C: needs Open4All (ROMPatcher+)'
                    if sid != 'qt-ssl' and status == 'documented' else None,
                    'patch_version': 'not stated by the author',
                }
            out.append(row)
        return out

    def _device_states(self, saved: dict) -> dict:
        return saved.get('tls', {})

    # ---- actions ---------------------------------------------------------------------------------
    def state(self, data):
        row, rows, facts = self.service._context(data)
        saved = self.service._load('observations', facts['key']) if facts['key'] else {}
        states = self._device_states(saved)
        comps = []
        for key, c in self.components.items():
            comps.append({'id': key, **{k: c[k] for k in ('title', 'role', 'name', 'size', 'sha256', 'version', 'released',
                          'author', 'homepage', 'source_repository', 'licence', 'release_notes', 'release_notes_text',
                          'depends_on', 'risk', 'observed_at', 'url')},
                          'cached': self._cached(c) is not None,
                          'device': states.get(key, {'state': 'unknown'})})
        return {'device': (row or {}).get('id'), 'reason': None if row else ('no-connection' if not rows else 'device-not-selected'),
                'components': comps, 'stacks': {k: {kk: vv for kk, vv in v.items()} for k, v in STACKS.items()},
                'app_kinds': {k: {'title': v['title'], 'stack': v['stack']} for k, v in APP_KINDS.items()},
                'applicability': self.applicability(), 'https': states.get('https-test', {'state': 'not-tested'}),
                'ssl_backup': states.get('ssl-original-backup', {'state': 'not-tested'}),
                'test_hosts': list(TEST_HOSTS),
                'statement': 'Applicability is the author\'s documentation, not a test on your phone. Installed means what you reported.'}

    def fetch(self, data):
        spec = self._spec(data.get('component'))
        raw = self._cached(spec)
        if raw is None:
            raw = self._download(spec)
            self._store(spec, raw)
        return {'component': data['component'], 'cached': True, 'validation': validate_component(spec, raw),
                'sha256': spec['sha256'], 'size': spec['size']}

    def _download(self, spec) -> bytes:
        public_https(spec['url'], hosts=HOSTS)
        request = urllib.request.Request(spec['url'], headers={'User-Agent': 'SymPort-TLS/1', 'Accept-Encoding': 'identity'})
        try:
            with self.opener.open(request, timeout=20) as response:
                public_https(response.geturl(), hosts=HOSTS)
                raw = response.read(spec['size'] + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ValueError('offline: the author\'s host is unreachable; nothing was accepted. Import the file manually instead.') from exc
        validate_component(spec, raw)  # raises hash-mismatch / broken-package; nothing is stored
        return raw

    def _store(self, spec, raw):
        path = self._path(spec)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(raw)

    def import_file(self, data):
        try:
            raw = base64.b64decode(data.get('content', ''), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('broken-package: content is not valid base64') from exc
        if not raw or len(raw) > MAX_PACKAGE:
            raise ValueError('broken-package: empty or too large')
        digest = sha(raw)
        spec_key = next((k for k, c in self.components.items() if c['sha256'] == digest), None)
        if spec_key is None:
            name = str(data.get('name', '')).lower()
            hint = next((k for k, c in self.components.items() if c['name'].lower() == name), None)
            raise ValueError('hash-mismatch: this file is not a pinned build' + (f' of {hint}' if hint else '')
                             + ' (newer or different build); review it in Certificate Inspector and update the pin')
        spec = self.components[spec_key]
        validation = validate_component(spec, raw)
        self._store(spec, raw)
        return {'component': spec_key, 'sha256': digest, 'validation': validation}

    def diagnose(self, data):
        host = str(data.get('host') or TEST_HOSTS[0]).lower()
        if not HOST.fullmatch(host):
            raise ValueError('Enter a public host name')
        probe = self.probe(host)
        server_utc = datetime.now(UTC)
        clock = {'ran_on': 'manual', 'server_utc': server_utc.isoformat(timespec='seconds'), 'phone_date': None,
                 'skew_days': None, 'verdict': 'unknown', 'source': 'manual'}
        phone = str(data.get('phone_date') or '')
        if phone:
            try:
                typed = date.fromisoformat(phone)
            except ValueError as exc:
                raise ValueError('Phone date must be YYYY-MM-DD') from exc
            skew = (typed - server_utc.date()).days
            clock.update(phone_date=phone, skew_days=skew, verdict='ok' if abs(skew) <= 1 else 'needs-action')
            leaf = probe.get('leaf') or {}
            nb, na = _cert_time(leaf.get('not_before')), _cert_time(leaf.get('not_after'))
            if nb and na:
                inside = nb.date() <= typed <= na.date()
                clock['certificate_window'] = 'phone-date-inside' if inside else 'phone-date-outside'
                if not inside:
                    clock['verdict'] = 'needs-action'
        return {'host': host,
                'server_probe': {'ran_on': 'server', **probe,
                                 'meaning': 'A modern client on the SymPort server reached the host. This says nothing about what the phone can do.'},
                'bridge_probe': {'ran_on': 'bridge', 'status': 'not-available', 'reason': 'The Windows Bridge has no HTTPS test action.'},
                'phone_test': {'ran_on': 'phone', 'status': 'manual',
                               'instructions': {'en': f'Open https://{host}/ in the phone browser or the app under test and record the result.',
                                                'ru': f'Откройте https://{host}/ в браузере телефона или в проверяемом приложении и запишите результат.'}},
                'clock': clock,
                'chain': {'status': 'leaf-only', 'reason': 'Only the leaf certificate is exposed; the full chain is not evaluated here.'},
                'at': now()}

    # ---- kit ---------------------------------------------------------------------------------------
    def kit(self, data):
        keys = data.get('components')
        if not isinstance(keys, list) or not keys or len(keys) > 4:
            raise ValueError('Choose components')
        order = []
        for k in keys:
            spec = self._spec(k)
            for dep in spec['depends_on']:
                if dep not in order:
                    order.append(dep)
            if k not in order:
                order.append(k)
        app = data.get('app_kind')
        if app is not None and app not in APP_KINDS:
            raise ValueError('Unknown application kind')
        row, rows, facts = self.service._context(data)
        total = sum(self.components[k]['size'] for k in order)
        facts['required_free'] = 2 * total + PLANNING_MARGIN
        evaluated = C.evaluate(facts, 'network-certs')
        saved = self.service._load('observations', facts['key']) if facts['key'] else {}
        states = self._device_states(saved)
        gate = [evaluated[c] for c in ('connection', 'identity', 'platform', 'storage', 'files', 'transfer', 'restore')]
        steps = []
        for k in order:
            spec = self.components[k]
            installed = states.get(k, {}).get('state', 'unknown')
            step = {'id': k, 'title': spec['title'], 'risk': spec['risk'], 'version': spec['version'], 'sha256': spec['sha256'],
                    'size': spec['size'], 'licence': spec['licence']['spdx'], 'device': states.get(k, {'state': 'unknown'}),
                    'obtained': self._cached(spec) is not None,
                    'transfer': {'execution': 'bridge-transfer', 'status': C.worst([g['status'] for g in gate])},
                    'install': {'execution': 'manual-on-phone', 'steps': self._guide(k)},
                    'restore': self._restore(k), 'result': installed}
            if spec['role'] == 'system-replacement':
                backup = states.get('ssl-original-backup', {}).get('state')
                rights = facts.get('rights')
                firmware = evaluated['firmware']
                needs = []
                if not rights or rights['scope'] != 'device':
                    needs.append({'en': 'Record device-level installation rights (InstallServer + Open4All patches) in Revive.',
                                  'ru': 'Запишите права установки уровня устройства (патчи InstallServer и Open4All) в Revive.'})
                if backup != 'installed':
                    needs.append({'en': 'Copy the original C:\\sys\\bin\\ssl.dll to the card with X-plore and record that you did.',
                                  'ru': 'Скопируйте оригинальный C:\\sys\\bin\\ssl.dll на карту через X-plore и запишите это.'})
                if firmware['status'] != 'ready':
                    needs.append({'en': 'The exact firmware must be reported by the device.', 'ru': 'Точная прошивка должна быть сообщена устройством.'})
                if evaluated['identity']['status'] != 'ready':
                    needs.append({'en': 'The exact model must be identified from the device.', 'ru': 'Точная модель должна определяться по устройству.'})
                step['high_risk'] = {'status': 'ready' if not needs else 'needs-action', 'requirements': needs,
                                     'privileged_adapter': 'not-available',
                                     'statement': {'en': 'SymPort has no tested privileged adapter: it can only copy the archive. Extraction into C:\\sys\\bin is done by you on the phone and cannot be undone by SymPort.',
                                                   'ru': 'У SymPort нет проверенного привилегированного адаптера: он может только скопировать архив. Распаковку в C:\\sys\\bin делаете вы на телефоне, SymPort её не откатывает.'}}
            steps.append(step)
        stack = APP_KINDS[app]['stack'] if app else None
        return {'device': (row or {}).get('id'), 'reason': None if row else ('no-connection' if not rows else 'device-not-selected'),
                'checks': gate, 'steps': steps, 'app_kind': app, 'stack': stack,
                'stack_support': self._stack_support(stack, facts) if stack else None,
                'required_free': facts['required_free'], 'dry_run': True,
                'statement': 'Preparation only. Copying files is not installation, and nothing is marked fixed until you retest.'}

    def _stack_support(self, stack, facts):
        profile = facts['identity']['profile']
        if not profile:
            return {'status': 'unknown', 'reason': {'en': 'The phone model is not identified.', 'ru': 'Модель телефона не определена.'}}
        row = next((r for r in self.applicability() if r['target'] == profile['id']), None)
        if not row:
            return {'status': 'unknown', 'reason': {'en': 'No applicability data for this model.', 'ru': 'Нет данных о применимости для этой модели.'}}
        s = row['stacks'][stack]
        via = STACKS[stack].get('via')
        return {**s, 'covered_by': via}

    @staticmethod
    def _guide(key):
        if key == 'mbedtls-lib':
            return [{'en': 'Open the copied MBedTLS.sis from SymPort-TLS in the phone file manager. An unsigned SIS needs the InstallServer patch.',
                     'ru': 'Откройте скопированный MBedTLS.sis из SymPort-TLS в файловом менеджере телефона. Неподписанному SIS нужен патч InstallServer.'},
                    {'en': 'Read the installer prompts. Record what you saw; do not assume it worked.',
                     'ru': 'Прочитайте запросы установщика. Запишите, что увидели; не считайте, что получилось.'}]
        return [{'en': 'Install MBedTLS first (the patch depends on mbedtls.dso).', 'ru': 'Сначала установите MBedTLS (патч зависит от mbedtls.dso).'},
                {'en': 'Copy the original C:\\sys\\bin\\ssl.dll somewhere safe and record its size.', 'ru': 'Скопируйте оригинальный C:\\sys\\bin\\ssl.dll в безопасное место и запишите его размер.'},
                {'en': 'With X-plore (Open4All active) extract ssl.zip to the root of C:. This replaces ssl.dll.',
                 'ru': 'В X-plore (при активном Open4All) распакуйте ssl.zip в корень C:. Это заменит ssl.dll.'},
                {'en': 'Restart the phone and retest HTTPS in the app that failed.', 'ru': 'Перезагрузите телефон и повторите HTTPS-проверку в проблемном приложении.'}]

    @staticmethod
    def _restore(key):
        if key == 'mbedtls-lib':
            return {'en': 'Uninstall MBedTLS in the phone application manager. Apps that need it will stop working.',
                    'ru': 'Удалите MBedTLS в диспетчере приложений телефона. Приложения, которым она нужна, перестанут работать.'}
        return {'en': 'Copy your saved original ssl.dll back to C:\\sys\\bin with X-plore. SymPort cannot restore system files.',
                'ru': 'Верните сохранённый оригинал ssl.dll в C:\\sys\\bin через X-plore. SymPort не восстанавливает системные файлы.'}

    # ---- records ---------------------------------------------------------------------------------
    def record(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that this is what you observed on the phone')
        item = data.get('item')
        if item not in RECORDABLE:
            raise ValueError('Unknown item')
        state = data.get('state')
        if item == 'https-test':
            if state not in ('pass', 'fail', 'not-tested'):
                raise ValueError('Invalid result')
            extra = {'host': str(data.get('host') or '')[:120], 'where': 'phone'}
        else:
            if state not in INSTALL_STATES:
                raise ValueError('Invalid state')
            extra = {}
        if item == 'ssl-original-backup' and state not in ('installed', 'not-tested'):
            raise ValueError('Record the backup as done or not tested')
        row, facts = self.service._need_device(data)
        saved = self.service._load('observations', facts['key'])
        if item in ('https-test', 'ssl-original-backup'):
            stored = state
        else:
            stored = state + '-reported' if state != 'not-tested' else state
        saved.setdefault('tls', {})[item] = {'state': stored, 'at': now(), 'source': 'manual', **extra}
        self.service._save('observations', facts['key'], saved)
        return {'item': item, 'record': saved['tls'][item]}


class _Redirects(Redirects):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_https(newurl, hosts=HOSTS)
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)
