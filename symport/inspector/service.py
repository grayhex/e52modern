"""Read-only package diagnosis, persisted evidence and explicit hand-off to Lab/phone."""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

from symport.analysis import e32
from symport.catalog.packages import validate_package
from symport.catalog.service import save
from symport.sis import reader

from .signatures import inspect_signatures

HEX = re.compile(r'^[a-f0-9]{32}$')
ERRORS = {
 'expired-certificate': ['Check the real phone date/time first. An expired certificate is not proof of a bad signature.', 'Prefer an updated package or an authorised re-signing certificate. Do not leave the phone clock incorrect; restore it after a deliberate offline diagnostic.'],
 'invalid-certificate': ['Check package integrity, issuer trust, certificate constraints and device binding. Re-download from the publisher.'],
 'restricted-capabilities': ['Package requests privileged capabilities; certificate authorisation and phone policy must be checked. Self-signing does not grant these privileges on stock firmware.'],
 'missing-capabilities': ['Compare requested capabilities with the authorising certificate and firmware policy. A self-signed certificate cannot grant restricted capabilities on stock firmware.'],
 'unsupported-os': ['Use a SIS for Symbian 9.x / S60 3rd FP2 and ARMv5. A signature or system patch cannot make an incompatible binary compatible.'],
 'missing-dependency': ['Install the publisher-documented dependency version. Dependency presence/version cannot be inferred from a file on a memory card.'],
 'unsigned-package': ['Review App Manager → Settings → Software installation on the phone. “All” does not grant restricted capabilities.', 'Prefer a publisher-signed package or your own authorised signing identity. Jailbreak Manager is a separate opt-in manual workflow, never enabled by Catalog.'],
 'unknown': ['Record the exact installer message and inspect the package. Do not infer a certificate error from an emulator crash.']}


def diagnose(message):
    if not isinstance(message, str) or len(message) > 2000:
        raise ValueError('Installer message must be up to 2000 characters')
    text = message.casefold()
    patterns = [('expired-certificate', ('expired', 'истёк', 'истек')), ('missing-capabilities', ('capabilit', 'возможност', 'доступ не разреш')), ('unsupported-os', ('unsupported os', 'not compatible', 'несовместим')), ('missing-dependency', ('dependenc', 'зависим')), ('invalid-certificate', ('certificate', 'сертификат')), ('unsigned-package', ('unsigned', 'не подпис'))]
    code = next((code for code, words in patterns if any(w in text for w in words)), 'unknown')
    return {'code': code, 'basis': 'user-supplied installer message; heuristic diagnosis', 'recommendations': ERRORS[code]}


class Inspector:
    def __init__(self, repo, resolver, devices, lab):
        self.root, self.resolver, self.devices, self.lab = repo / 'build/symport/inspector', resolver, devices, lab

    def report(self, key):
        if not isinstance(key, str) or not HEX.fullmatch(key):
            raise ValueError('Invalid inspection ID')
        import json
        return json.loads((self.root / (key+'.json')).read_text())

    def package(self, key):
        report = self.report(key)
        raw = (self.root / (key+'.sis')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != report['sha256']:
            raise ValueError('Inspected package integrity changed')
        return report, raw

    def execute(self, data):
        action = data.get('action')
        if action == 'diagnose':
            return diagnose(data.get('message'))
        if action == 'report':
            return self.report(data.get('id'))
        if action == 'list':
            import json
            return {'reports': [json.loads(p.read_text()) for p in sorted(self.root.glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)[:30]]}
        if action in ('emulate', 'transfer'):
            report, raw = self.package(data.get('id'))
            if data.get('confirm') is not True:
                raise ValueError('Explicit confirmation required')
            if action == 'emulate':
                result = self.lab.execute({'action': 'test', 'source': 'upload', 'name': report['name'], 'content': base64.b64encode(raw).decode(), 'kind': report.get('kind', 'app'), 'code': data.get('code'), 'confirm': True})
                report['emulator_report'] = result['id']
                save(self.root / (report['id']+'.json'), report)
                return result
            if report.get('emulator_report'):
                evidence = self.lab.report(report['emulator_report'])
                if evidence.get('running'):
                    raise ValueError('Wait for the emulator test')
            else:
                evidence = None
            if not evidence or evidence.get('install') != 'installed':
                if data.get('ack_unverified') is not True:
                    raise ValueError('Emulator installation is unverified; explicit acknowledgement required')
            result = self.devices.execute({'action': 'software-transfer', 'device': data.get('device'), 'path': data.get('path'), 'content': base64.b64encode(raw).decode(), 'confirm': True})
            report['transfer'] = {'status': result.get('status'), 'physical_installation': 'not-tested'}
            save(self.root / (report['id']+'.json'), report)
            return result
        if action != 'analyze':
            raise ValueError('Unknown inspector operation')
        name, raw, hint = self.resolver(data)
        validate_package(name, raw)
        if Path(name).suffix.lower() not in ('.sis', '.sisx'):
            raise ValueError('Certificate Inspector supports SIS/SISX, not JAR/JAD')
        at = datetime.fromisoformat(data['at']) if data.get('at') else datetime.now(UTC)
        at = at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC)
        info, signatures = reader.inspect(raw), inspect_signatures(raw, at)
        target = data.get('target', {})
        if not isinstance(target, dict):
            raise ValueError('Target must be an object')
        target = {k: str(target.get(k, ''))[:120] for k in ('model', 'rm', 'firmware', 'os')}
        is_e52 = bool(re.search(r'\bE52\b', target['model'], re.I))
        report = {'schema': 'symport.inspector/1', 'id': secrets.token_hex(16), 'name': name,
                  'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'package': info['package'],
                  'kind': 'theme' if hint == 'theme' or data.get('kind') == 'theme' else 'app',
                  'signatures': signatures, 'sis_checksums': {k:info[k] for k in ('uid_checksum_ok','controller_crc_ok','data_crc_ok')}, 'target': target, 'target_evidence': 'user-selected profile; not device attestation',
                  'dependencies': signatures['dependencies'], 'binaries': [], 'capabilities': [], 'issues': [],
                  'compatibility': 'unknown', 'emulator': 'not-tested', 'physical_device': 'not-tested',
                  'limitations': ['Certificate mathematics does not establish trust on the phone. No phone root store, revocation or IMEI/SID/capability constraints were validated.', 'Dependency inventory and firmware DLL/ordinal exports are unknown unless separately supplied.', 'Embedded/conditional SIS blocks and multi-data-unit packages are not fully evaluated.']}
        issues = report['issues']
        if signatures['status'] in ('invalid', 'unsigned'):
            issues.append('invalid-certificate' if signatures['status'] == 'invalid' else 'unsigned-package')
        if any(c['validity'] == 'expired' for chain in signatures['chains'] for c in chain['certificates']):
            issues.append('expired-certificate')
        if any(c['validity'] == 'not-yet-valid' for chain in signatures['chains'] for c in chain['certificates']):
            issues.append('certificate-not-yet-valid')
        try:
            for path, blob in reader.extract(raw).items():
                if e32.is_e32(blob):
                    binary = e32.analyze(blob)
                    binary['target'] = path
                    report['binaries'].append(binary)
                    report['capabilities'] += binary.get('capabilities') or []
                    if binary.get('restricted_capabilities'):
                        issues.append('restricted-capabilities')
                    if binary['kernel'] != 'eka2' or (is_e52 and binary['cpu'] not in ('armv4', 'armv5')):
                        issues.append('unsupported-os')
        except ValueError as exc:
            report['limitations'].append(str(exc))
        if target['os'] and target['os'] != '9.3':
            report['limitations'].append('Only the Nokia E52 Symbian 9.3 static target is evaluated by this screen.')
        from symport.analysis.compat import FirmwareProfile, evaluate
        from symport.devices.profiles import load_profile
        from symport.report import Report
        firmware = None
        provided = data.get('firmware_profile')
        if provided is not None:
            if not isinstance(provided, dict) or len(str(provided)) > 1024*1024 or provided.get('schema') != 1:
                raise ValueError('Invalid firmware profile')
            if provided.get('device') != 'nokia-e52' or provided.get('firmware_version') != target['firmware'] or not re.search(r'\bE52\b', target['model'], re.I):
                raise ValueError('Firmware profile must match the selected model and exact firmware version')
            dlls = provided.get('dlls')
            if not isinstance(dlls, dict) or len(dlls) > 10000:
                raise ValueError('Invalid firmware export inventory')
            for name, value in dlls.items():
                ordinals = value.get('ordinals') if isinstance(value, dict) else None
                if len(name) > 160 or (ordinals is not None and (not isinstance(ordinals, list) or len(ordinals) > 4096 or any(type(o) is not int or not 0 <= o <= 65535 for o in ordinals))):
                    raise ValueError('Invalid DLL ordinal inventory')
            firmware = FirmwareProfile(str(provided.get('id', 'user-profile')), 'nokia-e52', target['firmware'], str(provided.get('source', 'user-supplied')),
                                       {k.lower(): set(v['ordinals']) if isinstance(v, dict) and isinstance(v.get('ordinals'), list) else None for k,v in dlls.items()})
            report['firmware_profile'] = {'id': firmware.id, 'source': firmware.source, 'evidence': 'user-supplied; not device-attested'}
        if not is_e52:
            report['limitations'].append('Model profile unknown; Nokia E52 compatibility is not inferred for another model.')
        profile = load_profile(Path(__file__).resolve().parents[2] / 'profiles/nokia-e52.toml')
        for binary in report['binaries']:
            checks = Report('inspector static compatibility')
            binary['compatibility'] = evaluate(binary, profile, firmware, checks) if is_e52 else 'unknown'
            binary['checks'] = checks.to_dict()['checks']
        report['capabilities'] = sorted(set(report['capabilities']))
        report['issues'] = list(dict.fromkeys(issues))
        report['compatibility'] = 'incompatible' if 'unsupported-os' in issues or signatures['status'] == 'invalid' else 'unknown'
        if report['binaries'] and firmware and all(b['compatibility'] == 'compatible' for b in report['binaries']) and not report['issues']:
            report['compatibility'] = 'compatible'
        report['compatibility_scope'] = 'static only; installation, certificate trust and runtime are not established'
        report['recommendations'] = {code: ERRORS.get(code, ['Check the phone clock against the real date/time and obtain a current certificate.']) for code in report['issues']}
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.root / (report['id']+'.sis')).write_bytes(raw)
        save(self.root / (report['id']+'.json'), report)
        return report
