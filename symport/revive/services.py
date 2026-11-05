"""Legacy Services Revival (#37): which old system endpoints exist, what replaces them, what is proven.

Read-only. SymPort never changes a phone setting: it lists endpoints, checks (from the SERVER, and
says so) that an allow-listed substitute host still answers and that its redirect still matches the
registry, and records the before/after values you set yourself. A URL that opens from the server
proves nothing about a Nokia phone; Belle (N8/E7) endpoints are never carried over to S60v3/S60v5.
"""
from __future__ import annotations

import json
import re
import socket
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from symport.catalog.service import now
from symport.phone.registry import registry

from . import checks as C

DATA = Path(__file__).with_name('services.json')
TARGETS = ('nokia-e52', 'nokia-e72', 'nokia-n95', 'nokia-n95-8gb', 'nokia-n97-mini')
STATUSES = ('available', 'manual-setup-required', 'not-confirmed', 'unsupported')
META = re.compile(r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]*content=["\']?\s*\d+\s*;\s*url=([^"\'>\s]+)', re.I)
CREDENTIALS = re.compile(r'://[^/\s]*@|[?&](?:token|key|password|passwd|secret|auth)=', re.I)
RESULTS = ('pass', 'fail', 'not-tested')


def load() -> dict:
    document = json.loads(DATA.read_text(encoding='utf-8'))
    if document.get('schema') != 1:
        raise ValueError('Unsupported services registry')
    ids = [s['id'] for s in document['services']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate service id')
    for s in document['services']:
        sub = s.get('substitute')
        if sub and sub.get('final_url') and not str(sub['final_url']).startswith('https://'):
            raise ValueError('Substitutes must use HTTPS: ' + s['id'])
    return document


def default_probe(url: str, hosts: tuple, timeout: float = 8.0) -> dict:
    """GET without following redirects, TLS verified, at most 4 KiB, allow-listed hosts only."""
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in hosts or parts.port not in (None, 443) or parts.username:
        return {'ok': False, 'error': 'host-not-allow-listed'}
    try:
        answers = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return {'ok': False, 'error': 'dns'}
    import ipaddress
    if not answers or any(not ipaddress.ip_address(a[4][0]).is_global for a in answers):
        return {'ok': False, 'error': 'non-public-address'}

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(url, headers={'User-Agent': 'SymPort-Services/1', 'Accept-Encoding': 'identity'})
    try:
        with opener.open(request, timeout=timeout) as response:
            status, location, body = response.status, response.headers.get('Location'), response.read(4096)
    except urllib.error.HTTPError as exc:
        status, location, body = exc.code, exc.headers.get('Location'), b''
    except ssl.SSLError:
        return {'ok': False, 'error': 'tls-error'}
    except TimeoutError:
        return {'ok': False, 'error': 'timeout'}
    except (urllib.error.URLError, OSError):
        return {'ok': False, 'error': 'offline'}
    found = META.search(body.decode('utf-8', 'replace'))
    return {'ok': 200 <= status < 400, 'status': status, 'location': location, 'meta_refresh': found.group(1) if found else None}


class LegacyServices:
    def __init__(self, service):
        self.service = service
        self.data = load()
        self.probe = default_probe

    def _service(self, sid):
        for s in self.data['services']:
            if s['id'] == sid:
                return s
        raise ValueError('Unknown service')

    @staticmethod
    def status_for(svc: dict, target: dict) -> dict:
        explicit = svc['applies']['explicit_devices']
        if explicit and not any(e.lower().replace('nokia ', '') in target['name'].lower().replace('nokia ', '') for e in explicit):
            return {'status': 'unsupported', 'reason': {
                'en': 'The source file targets ' + ', '.join(explicit) + ' (Belle); it is not carried over to this S60 model.',
                'ru': 'Файл источника предназначен для ' + ', '.join(explicit) + ' (Belle); на эту модель S60 он не переносится.'}}
        if svc['apply_method'] == 'manual-setting':
            return {'status': 'manual-setup-required', 'reason': {
                'en': 'A user setting you change on the phone yourself; availability on this model is not tested.',
                'ru': 'Пользовательская настройка, которую вы меняете на телефоне сами; доступность на этой модели не проверена.'}}
        return {'status': 'not-confirmed', 'reason': {
            'en': svc['applies']['note'] + ' Nothing has been tested on this model.',
            'ru': 'Применимость не подтверждена источником; на этой модели ничего не проверялось.'}}

    def matrix(self) -> list[dict]:
        reg = registry()
        rows = []
        for tid in TARGETS:
            target = reg.get(tid)
            if not target:
                continue
            rows.append({'target': tid, 'name': target['name'], 'services': {
                s['id']: self.status_for(s, target) for s in self.data['services']}})
        return rows

    def state(self, data):
        row, rows, facts = self.service._context(data)
        saved = self.service._load('observations', facts['key']) if facts['key'] else {}
        profile = facts['identity']['profile']
        public = []
        for s in self.data['services']:
            sub = s.get('substitute') or {}
            public.append({k: s[k] for k in ('id', 'title', 'category', 'description', 'original_url', 'original_url_note', 'apply_method', 'requires')}
                          | {'origin': s['origin'], 'substitute': sub or None, 'host_probeable': sub.get('final_host') in self.data['allowed_probe_hosts'],
                             'record': saved.get('services', {}).get(s['id'])})
        return {'device': (row or {}).get('id'), 'reason': None if row else ('no-connection' if not rows else 'device-not-selected'),
                'profile': profile['id'] if profile else None, 'services': public, 'matrix': self.matrix(),
                'bridge': {'status': 'not-implemented', 'requirements': [
                    'allow-list of destinations', 'no open proxy', 'authentication', 'SSRF protection', 'no credential forwarding'],
                    'note': 'No self-hosted bridge is shipped; availability from a server is never proof that a Nokia phone works.'},
                'statement': self.data['note']}

    def diagnose(self, data):
        hosts = tuple(self.data['allowed_probe_hosts'])
        out = []
        for s in self.data['services']:
            sub = s.get('substitute')
            if not sub or not sub.get('entry'):
                out.append({'id': s['id'], 'status': 'not-probed', 'reason': 'no-substitute-url'})
                continue
            if sub.get('final_host') not in hosts and urlsplit(sub['entry']).hostname not in hosts:
                out.append({'id': s['id'], 'status': 'not-probed', 'reason': 'host-not-allow-listed',
                            'note': f"{sub.get('final_host')} is not probed (not allow-listed; check the spelling of the host)."})
                continue
            if sub['mechanism'] == 'html-meta-refresh' and not sub.get('final_url'):
                out.append({'id': s['id'], 'status': 'not-probed', 'reason': 'registry-has-no-target',
                            'note': 'The source file could not be read, so there is no redirect target to compare with.'})
                continue
            entry = self.probe(sub['entry'], hosts)
            result = {'id': s['id'], 'ran_on': 'server', 'entry': sub['entry'], 'probe': entry}
            if not entry.get('ok'):
                result['status'] = 'unreachable'
            elif sub['mechanism'] == 'html-meta-refresh':
                live = entry.get('meta_refresh')
                result['status'] = 'matches-registry' if live == sub['final_url'] else 'drifted' if live else 'no-redirect-found'
                result['live_target'] = live
            else:
                result['status'] = 'reachable'
            out.append(result)
        return {'ran_on': 'server', 'at': now(), 'results': out,
                'statement': 'Checked from the SymPort server with certificate verification. This says nothing about the phone: its clock, certificates and TLS support decide what a Nokia can open.'}

    def record(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that you changed this setting yourself')
        self._service(data.get('service'))
        before, after, result = str(data.get('before') or '')[:300], str(data.get('after') or '')[:300], data.get('result')
        if result not in RESULTS:
            raise ValueError('Invalid result')
        if CREDENTIALS.search(before + ' ' + after):
            raise ValueError('Do not record credentials or tokens; remove them from the value')
        row, facts = self.service._need_device(data)
        saved = self.service._load('observations', facts['key'])
        saved.setdefault('services', {})[data['service']] = {
            'before': before, 'after': after, 'result': result, 'at': now(), 'source': 'manual',
            'restore': {'en': 'Set the value back to: ' + (before or '(empty)'), 'ru': 'Верните значение: ' + (before or '(пусто)')}}
        self.service._save('observations', facts['key'], saved)
        return {'service': data['service'], 'record': saved['services'][data['service']]}

    def recommendations(self, facts) -> list[dict]:
        """Short, non-installing suggestions for the identified model (used by the Revive home)."""
        out = []
        c = C.evaluate(facts, 'network-certs')
        if c['identity']['status'] == 'ready':
            out.append({'id': 'check-clock-and-tls', 'area': 'network', 'title': {
                'en': 'Check the phone clock and TLS support first', 'ru': 'Сначала проверьте часы телефона и поддержку TLS'},
                'basis': 'documented: expired or wrong dates break HTTPS on old phones', 'action': 'network-certs'})
            out.append({'id': 'review-endpoints', 'area': 'services', 'title': {
                'en': 'Review old system endpoints and what replaces them', 'ru': 'Просмотрите старые системные адреса и чем они заменяются'},
                'basis': 'registry reviewed 2026-11-05; nothing applied automatically', 'action': 'legacy-services'})
        return out
