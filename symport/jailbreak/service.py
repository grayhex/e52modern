"""Experimental, fail-closed phone workflow. Never installs or patches through file transports."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import secrets
import stat
import threading
import zipfile
from pathlib import PurePosixPath

from symport.catalog.service import now, save
from symport.sis.writer import SisFile, SisPackage, build

GUIDE = 'https://lpcwiki.miraheze.org/wiki/Jailbreaking_S60_devices?oldid=71013'
METHODS = {
 'norton': {'name': 'Symantec / Norton', 'basis': 'Guide documents Symantec Symbian Hack for S60 3rd and later; the uploaded Norton package is not independently authenticated as its linked LDD package.', 'manual': ['Read the linked guide and record current clock, installer settings and existing patches.', 'Guide requires a SIM for Norton; install the selected SIS on the phone only after inspecting its certificate.', 'On the phone: Norton → AntiVirus → Quarantine list → Options → Restore all. This is a system-affecting manual step.', 'Guide then removes Symantec and uses ROMPatcher+. Confirm driver/firmware compatibility before proceeding. Do not enable Auto patches during an unverified first trial.']},
 'umu': {'name': 'UMU Nokia (archive method)', 'basis': 'Present in the supplied archive, not the documented Norton/Trend Micro payload in the linked guide. E52 firmware compatibility is unverified.', 'manual': ['UMU Nokia and UMU SE are different packages. UMU SE is not an E52 method.', 'No authenticated E52-specific UMU recovery procedure is available. Review manually; system automation is blocked.']},
 'rompatcher': {'name': 'ROMPatcher+ / InstallServer FP2', 'basis': 'Guide describes ROMPatcher+; a filename FP2 9.3 is a claim, not firmware validation.', 'manual': ['Inspect the exact package and patch hashes. Never apply a 5320/5800/N78/N79/N85/N96 patch to an E52.', 'Open ROMPatcher+ on the phone. Apply only a patch independently matched to your exact firmware. Record its visible status.', 'Do not replace C:/sys/bin/installserver.exe without a separately tested restoration procedure. SymPort cannot perform or reverse that system write.']}}
HEX = re.compile(r'^[0-9a-f]{32}$')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(raw, name):
    if len(raw) > 16 * 1024**2:
        raise ValueError('ZIP exceeds 16 MiB')
    entries = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        if len(infos) > 500 or sum(i.file_size for i in infos) > 64*1024**2:
            raise ValueError('ZIP expansion limit exceeded')
        seen = set()
        for i in infos:
            p = PurePosixPath(i.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in i.filename or ':' in i.filename or stat.S_ISLNK(i.external_attr >> 16) or i.filename in seen:
                raise ValueError('Unsafe or duplicate archive entry')
            seen.add(i.filename)
            if i.is_dir():
                continue
            # Keys are not read, hashed, retained, staged or used for signing.
            if p.suffix.lower() in ('.key', '.pem', '.p12', '.pfx'):
                entries.append({'name': i.filename, 'size': i.file_size, 'excluded': 'private-key-material'})
                continue
            if i.file_size > 8*1024**2:
                raise ValueError('Archive member exceeds 8 MiB')
            data = z.read(i)
            kind = 'sis' if p.suffix.lower() in ('.sis', '.sisx') else 'patch' if p.suffix.lower() == '.rmp' else 'binary' if p.suffix.lower() == '.exe' else 'reference'
            wrong = bool(re.search(r'3250|5500|9\.1|9\.2|e50|e61|5320|5800|6210|6220|n78|n79|n85|n96|samsung|umu se|\^3', i.filename, re.I))
            analysis = {}
            if kind == 'sis':
                from symport.inspector.signatures import inspect_signatures
                from symport.sis.reader import inspect
                try:
                    facts, signatures = inspect(data), inspect_signatures(data)
                    analysis = {'package': facts['package'], 'signature': signatures['status'], 'phone_trust': 'unknown',
                                'conditional_blocks': facts.get('undecoded_blocks', [])}
                except ValueError as exc:
                    analysis = {'signature': 'unsupported', 'reason': str(exc)[:200]}
            entries.append({'name': i.filename, 'sha256': sha(data), 'size': len(data), 'kind': kind,
                            'e52': 'incompatible-target-claim' if wrong else 'unverified',
                            'system_risk': kind in ('patch', 'binary') or 'hack' in i.filename.lower(), 'analysis': analysis, '_raw': data})
    return {'name': str(name)[:120], 'sha256': sha(raw), 'entries': entries, 'malware_scan': 'not-performed', 'firmware_validation': 'not-tested'}


class JailbreakManager:
    def __init__(self, repo, devices):
        self.root, self.devices, self.lock = repo/'build/symport/jailbreak', devices, threading.RLock()

    def path(self, kind, key):
        if not isinstance(key, str) or not HEX.fullmatch(key):
            raise ValueError('Invalid workflow ID')
        return self.root/kind/(key+'.json')

    def get(self, kind, key):
        return json.loads(self.path(kind, key).read_text(encoding="utf-8"))

    def record(self, run, action, status, **evidence):
        run['events'].append({'at': now(), 'action': action, 'status': status, **evidence})
        save(self.path('runs', run['id']), run)
        return run

    def execute(self, data):
        with self.lock:
            return self._execute(data)

    def _execute(self, data):
        action = data.get('action')
        if action == 'state':
            return {'methods': METHODS, 'guide': GUIDE, 'archives': [json.loads(p.read_text(encoding="utf-8")) for p in (self.root/'archives').glob('*.json')],
                    'runs': [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.root/'runs').glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)[:30]],
                    'system_automation': 'blocked', 'reason': 'No E52 firmware + system-write transport + tested recovery procedure has been validated. File transfer is not installation.'}
        if action == 'import':
            raw = base64.b64decode(data.get('content', ''), validate=True)
            try:
                result = inventory(raw, data.get('name', 'archive.zip'))
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                raise ValueError('Invalid, encrypted or unsupported ZIP archive') from exc
            result['id'] = secrets.token_hex(16)
            directory = self.root/'files'
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            for entry in result['entries']:
                payload = entry.pop('_raw', None)
                if payload is not None:
                    (directory/entry['sha256']).write_bytes(payload)
            save(self.path('archives', result['id']), result)
            return result
        if action == 'plan':
            method = data.get('method')
            if method not in METHODS:
                raise ValueError('Choose a documented method')
            identity = {k:str(data.get(k, ''))[:120] for k in ('model', 'rm', 'firmware', 'symbian')}
            if not identity['model'] or not identity['firmware']:
                raise ValueError('Record model and firmware, including unknown if unavailable')
            archive = self.get('archives', data.get('archive'))
            selected = data.get('files', [])
            if not isinstance(selected, list) or len(selected) > 40:
                raise ValueError('Invalid file selection')
            entries = [e for e in archive['entries'] if e.get('sha256') in selected and e.get('kind') in ('sis','patch','binary')]
            if len(entries) != len(set(selected)) or any(e['e52'] != 'unverified' or e.get('analysis', {}).get('signature') == 'invalid' for e in entries):
                raise ValueError('Excluded key, unsupported member or patch for another model selected')
            target_e52 = bool(re.search(r'\bE52\b', identity['model'], re.I)) and identity['symbian'] == '9.3'
            run = {'id': secrets.token_hex(16), 'schema': 'symport.jailbreak/1', 'created': now(), 'method': method, 'device': data.get('device'),
                   'identity': identity, 'identity_evidence': 'manual observation; file volume is not phone identity',
                   'archive': archive['sha256'], 'files': entries, 'events': [], 'staged': [], 'backup': None,
                   'applicability': 'candidate-only' if target_e52 else 'unknown', 'dry_run': True,
                   'system_automation': 'blocked', 'installation': 'not-tested', 'rollback_scope': 'Only unchanged files staged by this workflow; no system, app uninstall, clock or installer-setting rollback.',
                   'manual_steps': METHODS[method]['manual'], 'rollback_manual': ['On the phone, disable only patches enabled during this workflow and remove their Auto entries in ROMPatcher+.', 'Uninstall only packages added during the workflow using App Manager. Restore recorded clock and installer settings manually.', 'Any manually replaced system binary requires its original exact-version backup and a verified device recovery procedure; SymPort cannot promise recovery.'],
                   'initial_settings': str(data.get('settings', ''))[:2000], 'blocking_reasons': ['Exact firmware applicability is not validated.', 'USB/PC Bridge provides files, not protected system writes or installation.', 'No validated full recovery procedure.']}
            return self.record(run, 'plan', 'dry-run')
        run = self.get('runs', data.get('id'))
        if action == 'report':
            return run
        if action in ('install', 'patch', 'system-write', 'restore-system'):
            self.record(run, action, 'blocked')
            raise ValueError('System automation blocked: unknown exact firmware/transport/recovery. Use the reviewed manual scenario.')
        if action == 'backup':
            if data.get('confirm') is not True:
                raise ValueError('Confirm accessible-data backup')
            if run['backup']:
                return run
            result = self.devices.execute({'action': 'backup', 'device': run['device'], 'path': data.get('path', '')})
            raw = base64.b64decode(result['content'], validate=True)
            folder = self.root/'backups'
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            (folder/(run['id']+'.zip')).write_bytes(raw)
            run['backup'] = {'sha256': sha(raw), 'size': len(raw), 'scope': result.get('scope'), 'complete_phone_backup': False}
            return self.record(run, 'backup', 'saved-partial')
        if action == 'backup-export':
            raw = (self.root/'backups'/(run['id']+'.zip')).read_bytes()
            if sha(raw) != run['backup']['sha256']:
                raise ValueError('Backup integrity changed')
            return {'content': base64.b64encode(raw).decode(), 'name': 'unlock-accessible-data.zip'}
        if action == 'stage':
            if data.get('confirm') is not True or data.get('ack_risk') is not True or not run['backup']:
                raise ValueError('Backup and explicit risk/transfer confirmations required')
            if not run['files']:
                raise ValueError('Select files in a new dry-run plan before staging')
            if run.get('stage_started'):
                raise ValueError('Staging was already attempted; inspect report and rollback before a new plan')
            run['stage_started'] = True
            folder = 'SymPort-Unlock-'+run['id']
            self.devices.execute({'action': 'mkdir', 'device': run['device'], 'path': folder, 'confirm': True})
            self.record(run, 'stage', 'started')
            try:
                for index, entry in enumerate(run['files']):
                    raw = (self.root/'files'/entry['sha256']).read_bytes()
                    if sha(raw) != entry['sha256']:
                        raise ValueError('Source integrity changed')
                    suffix = PurePosixPath(entry['name']).suffix.lower()
                    filename = re.sub(r'[^A-Za-z0-9_.-]', '_', PurePosixPath(entry['name']).stem)[:90] or 'package'
                    path = folder+f'/{index:02d}-'+filename+suffix
                    staged = {'path': path, 'sha256': sha(raw), 'name': entry['name'], 'state': 'pending'}
                    run['staged'].append(staged)
                    self.record(run, 'stage-file', 'pending', sha256=sha(raw))
                    self.devices.execute({'action': 'upload', 'device': run['device'], 'path': path, 'content': base64.b64encode(raw).decode(), 'confirm': True})
                    echoed = self.devices.execute({'action': 'download', 'device': run['device'], 'path': path})
                    if sha(base64.b64decode(echoed['content'], validate=True)) != entry['sha256']:
                        raise ValueError('Transferred file read-back hash mismatch')
                    staged['state'] = 'transferred-not-installed'
                    self.record(run, 'stage-file', 'transferred-not-installed', sha256=sha(raw))
            except (ValueError, OSError) as exc:
                self.record(run, 'stage', 'partial-or-failed', error=str(exc)[:300])
                raise
            run['dry_run'] = False
            return self.record(run, 'stage', 'transferred-not-installed')
        if action == 'manual-step':
            if data.get('confirm_system') is not True or data.get('confirm') is not True:
                raise ValueError('Separate system-action confirmation required')
            step = data.get('step')
            if step not in ('install', 'quarantine-restore', 'apply-patch', 'disable-patch', 'uninstall', 'restore-settings', 'probe-install') or data.get('result') not in ('pass','fail','not-tested'):
                raise ValueError('Invalid manual observation')
            if not run['backup']:
                raise ValueError('Record a backup before system-affecting steps')
            return self.record(run, step, 'manual-observation', result=data['result'])
        if action == 'probe':
            raw = build(SisPackage(0xE0000810, 'SymPort safe installation probe', 'SymPort', files=[SisFile('!:\\data\\SymPort\\installation-probe.txt', b'SymPort installation probe. No executable, capabilities or patches.\r\n')]))
            return {'name': 'symport-installation-probe.sis', 'content': base64.b64encode(raw).decode(), 'sha256': sha(raw), 'scope': 'Unsigned, non-executable text payload. Installing it does NOT prove AllFiles or a jailbreak. Remove via App Manager.'}
        if action == 'rollback-plan':
            return {'id': run['id'], 'files': run['staged'], 'scope': run['rollback_scope'], 'manual': run['rollback_manual'], 'system_restore': 'unsupported'}
        if action == 'rollback':
            if data.get('confirm') is not True:
                raise ValueError('Confirm rollback of staged files')
            removed, conflicts = [], []
            for entry in run['staged']:
                if entry.get('removed'):
                    continue
                try:
                    download = self.devices.execute({'action': 'download', 'device': run['device'], 'path': entry['path']})
                    if sha(base64.b64decode(download['content'], validate=True)) != entry['sha256']:
                        conflicts.append(entry['path'])
                        continue
                    self.devices.execute({'action': 'delete', 'device': run['device'], 'path': entry['path'], 'confirm': True})
                    entry['removed'] = True
                    removed.append(entry['path'])
                except (ValueError, OSError):
                    conflicts.append(entry['path'])
            run['rollback'] = {'removed': removed, 'conflicts': conflicts, 'system_restored': False}
            return self.record(run, 'rollback', 'partial' if conflicts else 'staged-files-removed')
        raise ValueError('Unknown experimental workflow operation')
