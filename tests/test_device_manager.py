"""Real filesystem adapter and mock transport, including HTTP access checks."""
import base64
import json

import pytest

from symport.phone import DeviceManager
from symport.phone.bridge import PCBridge
from symport.phone.files import MountedVolumes
from tests.test_web import _http, http_server, repo  # noqa: F401


@pytest.fixture
def volume(tmp_path):
    root = tmp_path / 'phone'
    root.mkdir()
    return root, MountedVolumes({'usb': str(root)})


def test_files_roundtrip_and_confirmation(volume):
    root, adapter = volume
    assert adapter.devices()[0]['model'] is None
    args = {'device': 'usb', 'path': 'docs', 'confirm': True}
    adapter.execute(dict(args, action='mkdir'))
    args['path'] = 'docs/test.txt'
    content = base64.b64encode(b'phone data').decode()
    adapter.execute(dict(args, action='upload', content=content))
    assert adapter.execute(dict(args, action='download'))['content'] == content
    with pytest.raises(FileExistsError):
        adapter.execute(dict(args, action='upload', content=content))
    with pytest.raises(ValueError):
        adapter.execute(dict(args, action='delete', confirm=False))
    adapter.execute(dict(args, action='delete'))
    assert not (root / args['path']).exists()


def test_traversal_symlinks_and_invalid_sis(volume, tmp_path):
    root, adapter = volume
    for path in ('../secret', '/etc/passwd', 'a/../../secret', 'C:/secret', 'a\\secret'):
        with pytest.raises(ValueError):
            adapter.execute({'action': 'download', 'device': 'usb', 'path': path})
    (root / 'escape').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        adapter.execute({'action': 'list', 'device': 'usb', 'path': 'escape'})
    with pytest.raises(ValueError):
        adapter.execute({'action': 'transfer', 'device': 'usb', 'path': 'bad.sis',
                         'confirm': True, 'content': base64.b64encode(b'invalid').decode()})
    assert not (root / 'bad.sis').exists()


def test_mock_transport_and_private_history(tmp_path):
    class MockTransport:
        def devices(self):
            return []

        def execute(self, data):
            raise ValueError('private filename')
    manager = DeviceManager(tmp_path, MockTransport())
    assert manager.execute({'action': 'discover'})['devices'] == []
    with pytest.raises(ValueError):
        manager.execute({'action': 'upload', 'device': 'mock', 'content': 'sensitive'})
    log = manager.journal.read_text()
    assert 'sensitive' not in log and 'private filename' not in log
    assert json.loads(log)['status'] == 'failed'


def test_manager_http_requires_authentication(http_server):  # noqa: F811
    state, port = http_server
    assert _http(port, 'POST', '/api/manager', {'action': 'discover'})[0] == 403
    status, body = _http(port, 'POST', '/api/manager', {'action': 'discover'},
                         {'X-Symport-Token': state.token})
    assert status == 200 and json.loads(body)['devices'] == []
    assert _http(port, 'POST', '/api/bridge', {'action': 'discover'},
                 {'X-Symport-Token': state.token})[0] == 403


def test_bridge_requires_operator_configured_local_tunnel():
    for url in ('https://example.com', 'http://192.168.1.2', 'http://localhost/private'):
        with pytest.raises(ValueError):
            PCBridge(url, 'a' * 32)


def test_backup_restore_preview_conflicts_and_traversal(volume):
    import hashlib
    import io
    import zipfile
    root, adapter = volume
    (root / 'one.txt').write_text('private')
    backup = adapter.execute({'action': 'backup', 'device': 'usb', 'path': ''})
    (root / 'restore').mkdir()
    args = {'device': 'usb', 'path': 'restore', 'content': backup['content']}
    preview = adapter.execute(dict(args, action='restore-preview'))
    assert preview['changes'] == [{'name': 'one.txt', 'size': 7, 'conflict': False}]
    with pytest.raises(ValueError):
        adapter.execute(dict(args, action='restore', confirm=True, preview_sha256='wrong'))
    adapter.execute(dict(args, action='restore', confirm=True, preview_sha256=preview['sha256']))
    assert (root / 'restore' / 'one.txt').read_text() == 'private'
    with pytest.raises(ValueError):
        adapter.execute(dict(args, action='restore', confirm=True, preview_sha256=preview['sha256']))
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as archive:
        archive.writestr('../outside', 'bad')
    content = raw.getvalue()
    with pytest.raises(ValueError):
        adapter.execute(dict(args, content=base64.b64encode(content).decode(),
                             action='restore', confirm=True,
                             preview_sha256=hashlib.sha256(content).hexdigest()))


def test_gammu_identification_is_observed_not_invented(monkeypatch):
    from types import SimpleNamespace

    from symport.phone.local import LocalTransports
    monkeypatch.setenv('SYMPORT_GAMMU_CONFIG', '/operator/gammurc')
    # This exercises the CLI fallback, independently of an installed native binding.
    monkeypatch.setattr('symport.phone.gammu_adapter.gammu_native.available', lambda: False)
    monkeypatch.setattr('symport.phone.gammu_adapter.subprocess.run', lambda *a, **kw:
                        SimpleNamespace(stdout='Model : Nokia E52 (RM-469)\nFirmware : 091.004\nIMEI : private'))
    device = LocalTransports().devices()[-1]
    assert device['model'] == 'Nokia E52 (RM-469)' and device['rm'] == 'RM-469'
    assert 'private' not in json.dumps(device)


def test_bridge_key_and_end_to_end_files(http_server, monkeypatch, tmp_path):  # noqa: F811
    state, port = http_server
    key = 'k' * 48
    monkeypatch.setenv('SYMPORT_BRIDGE_KEY', key)
    state.devices.transport = MountedVolumes({'phone': str(tmp_path)})
    headers = {'X-Symport-Bridge-Key': key}
    status, body = _http(port, 'POST', '/api/bridge', {'action': 'discover'}, headers)
    assert status == 200 and json.loads(body)['devices'][0]['id'] == 'phone'
    status, body = _http(port, 'POST', '/api/bridge', {
        'action': 'upload', 'device': 'phone', 'path': 'data.txt', 'confirm': True,
        'content': base64.b64encode(b'roundtrip').decode()}, headers)
    assert status == 200
    status, body = _http(port, 'POST', '/api/bridge', {
        'action': 'download', 'device': 'phone', 'path': 'data.txt'}, headers)
    assert status == 200 and base64.b64decode(json.loads(body)['content']) == b'roundtrip'
    assert _http(port, 'POST', '/api/bridge', {'action': 'discover'},
                 {'X-Symport-Bridge-Key': 'wrong'})[0] == 403
