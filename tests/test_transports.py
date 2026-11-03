"""No hardware fixtures: prove protocol boundaries, staging and profile validation."""
import base64
import json
from pathlib import Path, PurePosixPath

import pytest

from symport.phone.connections import load_profiles
from symport.phone.models import documented_model
from symport.phone.obex import ObexAdapter, parse_listing, remote_path

PROFILE = dict(id='e52-ftp', name='Nokia E52 FTP', kind='obexftp', transport='bluetooth',
               manufacturer='Nokia', platform='S60', edition='3rd', address='AA:BB:CC:DD:EE:FF', channel=10)


def test_listing_standard_dtd_and_empty():
    raw = b'<?xml version="1.0"?><!DOCTYPE folder-listing SYSTEM "obex-folder-listing.dtd"><folder-listing><folder name="E:"/><file name="photo.jpg" size="123"/></folder-listing>'
    assert parse_listing(raw)[1] == {'name': 'photo.jpg', 'directory': False, 'size': 123, 'modified': None}
    assert parse_listing(b'<folder-listing version="1.0"/>') == []


@pytest.mark.parametrize('raw', [b'<folder-listing><file name="../x"/></folder-listing>', b'<folder-listing><file name="x" size="-1"/></folder-listing>', b'<!DOCTYPE x [<!ENTITY e "x">]><folder-listing/>', b'<folder-listing><file name="x"/><file name="x"/></folder-listing>', b'not xml'])
def test_listing_rejects_unsafe(raw):
    with pytest.raises(ValueError):
        parse_listing(raw)


@pytest.mark.parametrize('path', ['../x', '/C:/foo', 'a\\x', 'C:/../x', 'a//x', 'a\nx', 'E:/a:bad'])
def test_remote_path_rejects_escape(path):
    with pytest.raises(ValueError):
        remote_path(path)


def test_obex_stages_single_put_and_verifies():
    calls, stored = [], {}
    def run(args, cwd=None):
        calls.append(args)
        if args[0] == '--list':
            entries = ''.join(f'<file name="{PurePosixPath(k).name}" size="{len(v)}"/>' for k,v in stored.items() if str(PurePosixPath(k).parent) == args[1])
            return ('<folder-listing>' + entries + '</folder-listing>').encode()
        if '--put' in args:
            stored[args[1]] = Path(args[-1]).read_bytes()
        if '--get' in args:
            Path(args[1]).write_bytes(stored[args[-1]])
        return b''
    adapter = ObexAdapter(PROFILE, run)
    assert 'files-stage' in adapter.device()['capabilities']
    result = adapter.execute(dict(action='upload', path='E:/Images/a.txt', content=base64.b64encode(b'abc').decode(), confirm=True))
    assert result['status'] == 'verified-by-readback'
    assert result['destination'].startswith('E:/Images/SymPort-transfer-')
    puts = [c for c in calls if '--put' in c]
    assert len(puts) == 1 and puts[0][0] == '--output' and '--chdir' not in puts[0]
    assert stored[result['destination']] == b'abc'


def test_obex_refuses_system_or_unconfirmed_write():
    adapter = ObexAdapter(PROFILE, lambda *a: b'<folder-listing/>')
    for path, confirm in [('Z:/x', True), ('C:/sys/x', True), ('C:/private/x', True), ('E:/x', False)]:
        with pytest.raises(ValueError):
            adapter.execute(dict(action='upload', path=path, content='eA==', confirm=confirm))
    for action in ('delete', 'contacts-read', 'sms-send', 'mkdir'):
        with pytest.raises(ValueError):
            adapter.execute(dict(action=action, path=''))


def test_failed_stage_never_puts():
    calls = []
    def run(args, cwd=None):
        calls.append(args)
        if args[0] == '--mkdir':
            raise ValueError('stage failed')
        return b'<folder-listing/>'
    with pytest.raises(ValueError):
        ObexAdapter(PROFILE, run).execute(dict(action='upload', path='a.txt', content='eA==', confirm=True))
    assert not any('--put' in c for c in calls)


def test_opp_is_configured_not_discovered():
    adapter = ObexAdapter(dict(PROFILE, kind='obex-opp'), lambda *a: b'')
    d = adapter.device()
    assert d['connected'] is False and d['configured'] is True and 'files' not in d['capabilities']
    r = adapter.execute(dict(action='upload', path='a.txt', content='eA==', confirm=True))
    assert r['verification'] == 'receiver-acknowledgement-only'
    with pytest.raises(ValueError):
        adapter.execute(dict(action='upload', path='Installs/a.txt', content='eA==', confirm=True))


def test_profiles_strict_nokia_scope(tmp_path):
    path = tmp_path / 'connections.json'
    def save(row):
        path.write_text(json.dumps({'schema': 1, 'connections': [row]}))
    save(PROFILE)
    assert load_profiles(str(path))[0]['id'] == 'e52-ftp'
    for field, value in [('manufacturer', 'Sony Ericsson'), ('platform', 'S40'), ('channel', 0), ('address', 'host.invalid'), ('id', 'gammu')]:
        save(dict(PROFILE, **{field: value}))
        with pytest.raises(ValueError):
            load_profiles(str(path))
    assert documented_model('Nokia E52 (RM-469)')['s60'] == '3rd FP2'
    assert documented_model('Nokia 6300') is None
    path.write_text('[]')
    with pytest.raises(ValueError, match='JSON object'):
        load_profiles(str(path))


def test_obex_upstream_255_success_and_error_output(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv('SYMPORT_OBEXFTP_EXECUTABLE', 'operator-obexftp')
    def success(args, **kw):
        assert args[:3] == ['operator-obexftp', '--bluetooth', PROFILE['address']]
        kw['stdout'].write(b'<folder-listing/>')
        return SimpleNamespace(returncode=255)
    monkeypatch.setattr('symport.phone.obex.subprocess.run', success)
    assert ObexAdapter(PROFILE).device()['connected']
    def failed(args, **kw):
        kw['stderr'].write(b'failed: private phone path')
        return SimpleNamespace(returncode=255)
    monkeypatch.setattr('symport.phone.obex.subprocess.run', failed)
    row = ObexAdapter(PROFILE).device()
    assert not row['connected'] and 'private phone path' not in row['evidence']


def test_missing_opp_executable_is_not_capability(monkeypatch):
    monkeypatch.delenv('SYMPORT_OBEXFTP_EXECUTABLE', raising=False)
    monkeypatch.setattr('symport.phone.obex.shutil.which', lambda name: None)
    d = ObexAdapter(dict(PROFILE, kind='obex-opp')).device()
    assert not d['connected'] and d['capabilities'] == []


def test_known_model_profile_is_not_non_nokia_identity(tmp_path, monkeypatch):
    from symport.phone.gammu_adapter import GammuAdapter
    monkeypatch.setattr('symport.phone.gammu_adapter.gammu_native.available', lambda: True)
    adapter = GammuAdapter(tmp_path, 'usb', '/owner/config', kind='gammu-usb')
    adapter.personal.execute = lambda *args: {'model':'E52', 'manufacturer':'Another vendor', 'capability_status':{}}
    assert not adapter.device()['connected']
    with pytest.raises(ValueError, match='supported Nokia'):
        adapter.execute({'action':'personal-read'})
