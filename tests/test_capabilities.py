"""Capability matrix: per-connection, probe-backed, read never implies write. No phone needed."""
import base64
import os
import subprocess
from types import SimpleNamespace

import pytest

from symport.phone import DeviceManager, capabilities
from symport.phone.files import MountedVolumes
from symport.phone.gammu_adapter import GammuAdapter
from symport.phone.obex import ObexAdapter
from tests.test_transports import PROFILE


def state(row, op):
    return row['capability_matrix'][op]


def identify_only(monkeypatch, model='Nokia E52 (RM-469)'):
    monkeypatch.setattr('symport.phone.gammu_adapter.gammu_native.available', lambda: False)
    out = f'Manufacturer : Nokia\nModel        : {model}\nFirmware     : 071.004\n'
    monkeypatch.setattr(
        'symport.phone.gammu_adapter.subprocess.run',
        lambda *a, **k: SimpleNamespace(stdout=out),
    )


def test_gammu_identify_alone_never_promises_pim(tmp_path, monkeypatch):
    identify_only(monkeypatch)
    row = GammuAdapter(tmp_path, 'usb', '/owner/gammurc', kind='gammu-usb').device()
    assert row['connected'] and row['model'].startswith('Nokia E52')
    assert state(row, 'identity.read')['status'] == 'available'
    for op in ('contacts.read', 'calendar.read', 'tasks.read', 'sms.read'):
        assert state(row, op)['status'] == 'not-tested'
        assert 'identify' in state(row, op)['evidence']
    # The CLI export is a read-only path that may be tried (the read is the probe); SMS has none.
    assert state(row, 'calendar.read')['attempt'] == 'unverified'
    assert state(row, 'sms.read')['attempt'] == 'blocked'
    for name in ('contacts-read', 'calendar-read', 'personal-data', 'sms-send'):
        assert name not in row['capabilities']
    assert row['capability_status']['contacts']['status'] == 'unknown'
    assert state(row, 'identity.read')['source'] == 'gammu-cli:identify'
    assert state(row, 'identity.read')['checked_at']


def test_gammu_native_stores_are_separate(tmp_path, monkeypatch):
    monkeypatch.setattr('symport.phone.gammu_adapter.gammu_native.available', lambda: True)
    adapter = GammuAdapter(tmp_path, 'usb', '/owner/gammurc', kind='gammu-usb')
    adapter.personal.execute = lambda *a: {
        'model': 'Nokia E52', 'manufacturer': 'Nokia', 'battery': 80, 'sms_send_verified': False,
        'capability_status': {
            'contacts': {'status': 'available', 'reason': 'ok'},
            'calendar': {'status': 'unavailable', 'reason': 'ERR_NOTSUPPORTED'},
            'tasks': {'status': 'unavailable', 'reason': 'ERR_TIMEOUT'},
            'sms': {'status': 'unavailable', 'reason': 'ERR_NOTIMPLEMENTED'},
        },
    }
    row = adapter.device()
    assert state(row, 'contacts.read')['status'] == 'available'
    assert state(row, 'calendar.read')['status'] == 'unsupported'
    assert state(row, 'tasks.read')['status'] == 'error'
    assert 'ERR_TIMEOUT' in state(row, 'tasks.read')['evidence']
    assert state(row, 'sms.read')['status'] == 'unsupported'
    # Reading contacts proves neither a contact write nor SMS sending nor any file access.
    assert state(row, 'contacts.write')['status'] == 'not-tested'
    assert state(row, 'contacts.write')['attempt'] == 'confirmed-only'
    assert state(row, 'sms.send')['attempt'] == 'blocked'
    assert state(row, 'files.list')['status'] == 'unsupported'
    assert 'contacts-read' in row['capabilities'] and 'calendar-read' not in row['capabilities']
    assert 'personal-data' in row['capabilities'] and 'sms-send' not in row['capabilities']
    assert 'files' not in row['capabilities']
    assert state(row, 'telemetry.read')['status'] == 'available'


def test_gammu_connection_failure_marks_everything_error(tmp_path, monkeypatch):
    monkeypatch.setattr('symport.phone.gammu_adapter.gammu_native.available', lambda: True)
    adapter = GammuAdapter(tmp_path, 'usb', '/owner/gammurc', kind='gammu-usb')

    def fail(*a):
        raise ValueError('boom')

    adapter.personal.execute = fail
    monkeypatch.setattr(
        'symport.phone.gammu_adapter.subprocess.run',
        lambda *a, **k: (_ for _ in ()).throw(subprocess.SubprocessError()),
    )
    row = adapter.device()
    assert not row['connected'] and row['capabilities'] == []
    assert {s['status'] for s in row['capability_matrix'].values()} <= {'error', 'unsupported'}
    assert state(row, 'identity.read')['status'] == 'error'


def test_mass_storage_is_files_only(tmp_path):
    (tmp_path / 'a.txt').write_text('x')
    row = MountedVolumes({'card': str(tmp_path)}).devices()[0]
    assert state(row, 'files.list')['status'] == 'available'
    assert state(row, 'files.download')['status'] == 'available'
    for op in ('identity.read', 'telemetry.read', 'contacts.read', 'calendar.read', 'sms.read',
               'sms.send', 'apps.registry', 'install.run'):
        assert state(row, op)['status'] == 'unsupported', op
        assert state(row, op)['attempt'] == 'blocked'
    # Writes are never probed: possible with confirmation, but not "available".
    for op in ('files.upload', 'files.mkdir', 'files.delete', 'packages.transfer'):
        assert state(row, op)['status'] == 'not-tested'
        assert state(row, op)['attempt'] == 'confirmed-only'
    assert not (tmp_path / '.symport-probe').exists() and os.listdir(tmp_path) == ['a.txt']
    assert 'device-details' not in row['capabilities'] and 'personal-data' not in row['capabilities']
    assert {'files', 'files-upload', 'transfer'} <= set(row['capabilities'])


def test_read_only_volume_blocks_writes(tmp_path, monkeypatch):
    monkeypatch.setattr('symport.phone.files.os.access', lambda *a: False)
    row = MountedVolumes({'card': str(tmp_path)}).devices()[0]
    assert state(row, 'files.list')['status'] == 'available'
    assert state(row, 'files.upload')['status'] == 'unsupported'
    assert 'files-upload' not in row['capabilities'] and 'files' in row['capabilities']


def test_unmounted_volume_has_no_capabilities(tmp_path):
    row = MountedVolumes({'card': str(tmp_path / 'missing')}).devices()[0]
    assert not row['connected'] and row['capabilities'] == []
    assert state(row, 'files.list')['status'] == 'error'


def test_opp_acknowledgement_is_not_a_file_browser_or_install():
    row = ObexAdapter(dict(PROFILE, kind='obex-opp'), lambda *a: b'').device()
    assert state(row, 'packages.opp-push')['attempt'] == 'confirmed-only'
    for op in ('files.list', 'files.download', 'files.stage', 'packages.transfer', 'install.run'):
        assert state(row, op)['status'] == 'unsupported', op
    assert 'files' not in row['capabilities'] and 'opp-push' in row['capabilities']
    assert 'acceptance' in state(row, 'packages.opp-push')['evidence']


def test_obex_ftp_listing_is_the_only_proof():
    ok = ObexAdapter(PROFILE, lambda *a: b'<folder-listing/>').device()
    assert state(ok, 'files.list')['status'] == 'available'
    assert state(ok, 'files.stage')['status'] == 'not-tested'
    assert state(ok, 'files.delete')['status'] == 'unsupported'
    assert state(ok, 'identity.read')['status'] == 'unsupported'

    def down(args, cwd=None):
        raise ValueError('OBEX request failed (exit 255)')

    bad = ObexAdapter(PROFILE, down).device()
    assert state(bad, 'files.list')['status'] == 'error' and 'exit 255' in state(bad, 'files.list')['evidence']
    assert bad['capabilities'] == []


def test_fingerprint_changes_with_phone_transport_and_firmware():
    base = {'id': 'usb', 'transport': 'gammu', 'connection_kind': 'gammu-usb', 'model': 'E52', 'rm': 'RM-469', 'firmware': '1'}
    prints = {capabilities.fingerprint(dict(base, **change)) for change in (
        {}, {'model': 'E72'}, {'connection_kind': 'gammu-bluetooth'}, {'firmware': '2'}, {'id': 'bt'})}
    assert len(prints) == 5
    assert capabilities.fingerprint(base) == capabilities.fingerprint(dict(base, imei='123', battery=5))


class Fake:
    """Transport whose row can be swapped to simulate another phone or a disconnect."""

    def __init__(self, tmp_path):
        self.volume = tmp_path / 'card'
        self.volume.mkdir()
        self.roots = {'card': str(self.volume)}
        self.fingerprint = {}
        self.present = True

    def devices(self):
        if not self.present:
            return []
        row = MountedVolumes(self.roots).devices()[0]
        row.update(self.fingerprint)
        return [capabilities.apply(row, row['capability_matrix'])]

    def execute(self, data):
        return MountedVolumes(self.roots).execute(data)


def upload(manager, name='t.txt'):
    return manager.execute({'action': 'upload', 'device': 'card', 'path': name,
                            'content': base64.b64encode(b'x').decode(), 'confirm': True})


def test_confirmed_write_proves_that_operation_only_for_that_connection(tmp_path):
    transport = Fake(tmp_path)
    manager = DeviceManager(tmp_path, transport)
    row = manager.execute({'action': 'discover'})['devices'][0]
    assert state(row, 'files.upload')['status'] == 'not-tested'
    upload(manager)
    row = manager.execute({'action': 'discover'})['devices'][0]
    assert state(row, 'files.upload')['status'] == 'available'
    assert state(row, 'files.upload')['source'] == 'observed-operation'
    # One proven write does not prove the others.
    assert state(row, 'files.delete')['status'] == 'not-tested'
    # Another phone/firmware on the same connection id must not inherit the proof.
    transport.fingerprint = {'model': 'Nokia E72', 'transport': 'mounted-volume'}
    row = manager.execute({'action': 'discover'})['devices'][0]
    assert state(row, 'files.upload')['status'] == 'not-tested'
    transport.fingerprint = {}
    assert state(manager.execute({'action': 'discover'})['devices'][0], 'files.upload')['status'] == 'not-tested'


def test_disconnect_drops_proof_and_failed_write_proves_nothing(tmp_path):
    transport = Fake(tmp_path)
    manager = DeviceManager(tmp_path, transport)
    manager.execute({'action': 'discover'})
    with pytest.raises(ValueError):
        manager.execute({'action': 'upload', 'device': 'card', 'path': '../x', 'content': 'eA==', 'confirm': True})
    assert state(manager.execute({'action': 'discover'})['devices'][0], 'files.upload')['status'] == 'not-tested'
    upload(manager)
    transport.present = False
    assert manager.execute({'action': 'discover'})['devices'] == []
    transport.present = True
    row = manager.execute({'action': 'discover'})['devices'][0]
    assert state(row, 'files.upload')['status'] == 'not-tested'


def test_unverified_results_do_not_prove_writes():
    proofs = capabilities.ObservedWrites()
    row = {'id': 'x', 'connected': True, 'capability_fingerprint': 'f'}
    proofs.record(row, 'transfer', {'status': 'received-by-opp-not-installed'})
    proofs.record(row, 'sms-send', {'status': 'submitted-to-network'})
    proofs.record(dict(row, connected=False), 'upload', {'status': 'completed'})
    assert proofs.proofs == {}


def test_recheck_is_read_only_and_scoped(tmp_path):
    transport = Fake(tmp_path)
    manager = DeviceManager(tmp_path, transport)
    result = manager.execute({'action': 'capabilities', 'device': 'card'})
    assert result['device']['id'] == 'card' and result['device']['capability_matrix']
    assert list(transport.volume.iterdir()) == []
    with pytest.raises(ValueError, match='Unknown connection'):
        manager.execute({'action': 'capabilities', 'device': 'gone'})


def test_peer_without_matrix_is_not_trusted():
    row = capabilities.finalize({'id': 'old', 'connected': True, 'capabilities': ['files', 'transfer', 'contacts-read']})
    assert row['capabilities'] == []
    assert state(row, 'files.list')['status'] == 'not-tested'
    assert 'Bridge' in state(row, 'files.list')['evidence']


def test_peer_matrix_is_sanitised_and_cannot_forge_attempts():
    forged = {'files.list': {'status': 'unsupported', 'attempt': 'verified', 'source': 's' * 500},
              'sms.send': {'status': 'bogus'}, 'rm -rf': {'status': 'available'},
              'files.upload': {'status': 'available', 'attempt': 'blocked'}}
    row = capabilities.finalize({'id': 'p', 'connected': True, 'capability_matrix': forged})
    assert state(row, 'files.list')['attempt'] == 'blocked' and len(state(row, 'files.list')['source']) == 80
    assert 'rm -rf' not in row['capability_matrix']
    assert state(row, 'sms.send')['status'] == 'not-tested'
    assert state(row, 'files.upload')['attempt'] == 'verified'
    assert capabilities.finalize(dict(row))['capability_matrix'] == row['capability_matrix']


def test_every_adapter_output_is_a_complete_matrix(tmp_path, monkeypatch):
    identify_only(monkeypatch)
    rows = [
        GammuAdapter(tmp_path, 'usb', '/c', kind='gammu-usb').device(),
        ObexAdapter(PROFILE, lambda *a: b'<folder-listing/>').device(),
        MountedVolumes({'c': str(tmp_path)}).devices()[0],
    ]
    for row in rows:
        assert set(row['capability_matrix']) == set(capabilities.OPERATIONS)
        for op, item in row['capability_matrix'].items():
            assert item['status'] in capabilities.STATUSES and item['checked_at'] and item['source']
            assert item['mode'] == capabilities.OPERATIONS[op][0]
        assert row['capability_matrix']['install.run']['status'] == 'unsupported'
        assert row['capability_matrix']['apps.registry']['status'] == 'unsupported'
