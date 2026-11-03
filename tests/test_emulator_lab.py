"""MGO contract, authentication, durable evidence and physical-transfer boundaries."""
from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import threading
import time

import pytest

from symport.lab import EmulatorLab
from symport.lab.client import AgentError, MgoClient
from symport.phone.files import MountedVolumes
from symport.phone.service import DeviceManager
from tests.lab_fixture import TOKEN, MockMgo, serve_mock, sis
from tests.test_web import _http, http_server, repo  # noqa: F401


def wait(lab, report):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = lab.report(report['id'])
        if not result['running']:
            return result
        time.sleep(.01)
    pytest.fail('Lab operation did not complete')


@pytest.fixture
def setup(tmp_path):
    volume = tmp_path / 'volume'
    volume.mkdir()
    devices = DeviceManager(tmp_path, MountedVolumes({'phone': volume}))
    agent = MockMgo()
    lab = EmulatorLab(tmp_path, lambda data: ('fixture.sis', sis(data.get('theme', False)), 'app'), devices, agent)
    return lab, agent, volume


def run(lab, **values):
    return wait(lab, lab.execute(dict(action='test', source='upload', confirm=True, code='mock-device', **values)))


def test_install_launch_capture_and_transfer_identical_bytes(setup):
    lab, agent, volume = setup
    report = run(lab)
    assert report['status'] == report['launch'] == 'launched'
    assert report['install'] == 'installed' and report['physical_device'] == 'not-tested'
    assert report['firmware']['code'] == 'mock-device'
    assert report['package']['sha256'] == hashlib.sha256(sis()).hexdigest()
    assert report['screenshots'][0]['width'] == 240 and report['logs']
    assert all(e['stage'] for e in report['events'])
    with pytest.raises(ValueError, match='Подтвердите'):
        lab.execute({'action': 'transfer', 'id': report['id']})
    result = lab.execute({'action': 'transfer', 'id': report['id'], 'device': 'phone', 'path': 'fixture.sis', 'confirm': True})
    assert result['status'] == 'transferred-not-installed'
    assert (volume / 'fixture.sis').read_bytes() == sis()
    assert lab.report(report['id'])['physical_transfer']['installation'] == 'not-tested'
    (lab.root / 'packages' / (report['id'] + '.bin')).write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        lab.execute({'action': 'transfer', 'id': report['id'], 'confirm': True})
    agent.launch_state = 'crashed'
    lab.state()
    assert lab.report(report['id'])['launch'] == 'failed'


def test_theme_never_launches_uid_and_records_manual_observation(setup):
    lab, agent, _ = setup
    report = run(lab, theme=True)
    assert report['kind'] == 'theme' and report['status'] == 'installed'
    assert report['launch'] == 'unsupported' and 'вручную' in report['instructions']
    assert not any(path.endswith('/launch') for _, path, _ in agent.calls)
    lab.execute({'action': 'observe', 'id': report['id'], 'step': 'menu', 'result': 'pass'})
    saved = lab.report(report['id'])
    assert saved['observations'][0]['source'] == 'user-observation'
    assert len(saved['screenshots']) == 2 and saved['physical_device'] == 'not-tested'
    other = run(lab)
    with pytest.raises(ValueError, match='текущего'):
        lab.execute({'action': 'shot', 'id': report['id']})
    assert other['id'] != report['id']


@pytest.mark.parametrize('stage', ['install', 'launch', 'launching', 'ambiguous'])
def test_failure_does_not_claim_launch(setup, stage):
    lab, agent, _ = setup
    if stage == 'install':
        agent.fail_install = True
    if stage == 'launch':
        agent.launch_state = 'crashed'
    if stage == 'launching':
        agent.launch_state = 'launching'
    if stage == 'ambiguous':
        agent.added = [{'uid': '0x1'}, {'uid': '0x2'}]
    report = run(lab)
    assert report['launch'] != 'launched'
    assert report['install'] == ('failed' if stage == 'install' else 'installed')
    assert report['status'] == ('failed' if stage in ('install', 'launch') else 'installed')


def test_java_is_not_tested_in_symbian_and_has_no_unrelated_capture(setup):
    lab, agent, _ = setup
    lab.resolver = lambda data: ('game.jar', b'test-only', 'app')
    report = run(lab)
    assert report['status'] == report['install'] == 'unsupported'
    assert report['engine'] == 'not-run' and 'KEmulator' in report['alternative_engine']
    assert not report['screenshots'] and not agent.calls


def test_no_firmware_or_corrupt_sis_never_installs(setup):
    lab, agent, _ = setup
    agent.installed = False
    report = run(lab)
    assert report['install'] == 'not-tested' and report['status'] == 'failed'
    assert not any(path == '/v1/apps' and method == 'POST' for method, path, _ in agent.calls)
    lab.resolver = lambda data: ('bad.sis', b'corrupt', 'app')
    report = run(lab)
    assert report['install'] == 'not-tested' and report['status'] == 'failed'


def test_firmware_stream_provenance_bundle_and_install(setup):
    lab, agent, _ = setup
    bundle = lab.execute({'action': 'bundle'})['bundle']
    entries = [lab.upload_firmware(io.BytesIO(raw), len(raw), slot, name, bundle) for slot, name, raw in [('vpl', 'RM-469_001.vpl', b'<fixture/>'), ('fpsx', 'RM-469_001.fpsx', b'test-only')]]
    assert agent.uploads[0]['name'] == 'RM-469_001.vpl'
    assert entries[1]['sha256'] == hashlib.sha256(b'test-only').hexdigest()
    report = wait(lab, lab.execute({'action': 'install-firmware', 'uploads': [e['id'] for e in entries], 'variant': 0, 'confirm': True}))
    assert report['install'] == 'installed' and report['launch'] == 'not-tested'
    body = next(b for m, p, b in agent.calls if p == '/agent/firmware/install')
    assert body == {'bundle': bundle, 'vpl': 'RM-469_001.vpl', 'variant': 0}
    assert report['firmware_inputs'][1]['sha256'] == entries[1]['sha256']
    rom1 = lab.upload_firmware(io.BytesIO(b'one'), 3, 'rom', 'same.rom')
    rom2 = lab.upload_firmware(io.BytesIO(b'two'), 3, 'rom', 'same.rom')
    assert rom1['agent_file'] != rom2['agent_file'] and rom1['name'] == rom2['name']


@pytest.mark.parametrize('slot,name,length,bundle', [('rom', '../x', 1, None), ('vpl', 'x.vpl', 1, None), ('vpl', 'x.vpl', 5*1024**2, 'a'*32), ('fpsx', 'x.fpsx', 0, 'a'*32), ('archive', 'x.zip', 2*1024**3+1, None), ('unknown', 'x', 1, None)])
def test_invalid_firmware_rejected_before_agent(setup, slot, name, length, bundle):
    lab, agent, _ = setup
    with pytest.raises(ValueError):
        lab.upload_firmware(io.BytesIO(b'x'), length, slot, name, bundle)
    assert not agent.uploads


def test_incomplete_bundle_and_agent_job_failure(setup):
    lab, agent, _ = setup
    e = lab.upload_firmware(io.BytesIO(b'x'), 1, 'fpsx', 'x.fpsx', 'a'*32)
    r = wait(lab, lab.execute({'action': 'install-firmware', 'uploads': [e['id']], 'confirm': True}))
    assert r['install'] == 'failed'
    rom = lab.upload_firmware(io.BytesIO(b'x'), 1, 'rom', 'x.rom')
    agent.job_failure = 'Invalid ROM: test fixture'
    r = wait(lab, lab.execute({'action': 'install-firmware', 'uploads': [rom['id']], 'confirm': True}))
    assert r['status'] == r['install'] == 'failed' and 'Invalid ROM' in r['error']


def test_restart_preserves_reports_firmware_uploads_and_interrupts_pending(setup, tmp_path):
    lab, agent, _ = setup
    report = run(lab, theme=True)
    pending = lab._new('session')
    entry = lab.upload_firmware(io.BytesIO(b'x'), 1, 'rom', 'x.rom')
    restarted = EmulatorLab(tmp_path, lab.resolver, lab.devices, agent)
    assert restarted.report(report['id'])['install'] == 'installed'
    assert restarted.report(pending['id'])['status'] == 'not-tested'
    assert not restarted.report(pending['id'])['running']
    assert restarted.uploads[entry['id']]['sha256'] == entry['sha256']


def test_controls_allowlist_report_paths_and_confirm(setup):
    lab, agent, _ = setup
    for data in [{'action': 'key', 'key': 'shell', 'event': 'down'}, {'action': 'report', 'id': '../secret'}, {'action': 'test'}, {'action': 'select', 'code': '../../bad'}, {'action': 'exec'}]:
        with pytest.raises(ValueError):
            lab.execute(data)
    lab.execute({'action': 'key', 'key': 'applications', 'event': 'down'})
    lab.execute({'action': 'release'})
    assert agent.calls[-1][1] == '/v1/input/release'


def test_real_http_client_token_rotation_stream_and_error_mapping(monkeypatch, tmp_path):
    agent = MockMgo()
    server = serve_mock(agent)
    token = tmp_path / 'key'
    token.write_text(TOKEN)
    monkeypatch.setenv('SYMPORT_MGO_URL', f'http://127.0.0.1:{server.server_port}')
    monkeypatch.setenv('SYMPORT_MGO_TOKEN_FILE', str(token))
    client = MgoClient()
    try:
        assert client.request('GET', '/agent/health')['ok']
        client.upload('/agent/firmware/rom', 'test.rom', io.BytesIO(b'raw-file'), 8)
        assert agent.uploads[0]['raw'] == b'raw-file'
        with pytest.raises(AgentError, match='surface') as error:
            client.request('GET', '/v1/screenshot?region=guest', binary=True)
        assert error.value.status == 409 and error.value.code == 'no_screen'
        token.write_text('wrong-test-token-value')
        with pytest.raises(AgentError) as error:
            client.request('GET', '/agent/health')
        assert error.value.status == 401 and TOKEN not in str(error.value)
        token.write_text(TOKEN)
        assert client.request('GET', '/agent/health')['ok']
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize('url', ['https://evil.example', 'http://mgo-symbian/path', 'http://user:secret@mgo-symbian', 'file:///etc/passwd'])
def test_agent_url_cannot_be_arbitrary_proxy(monkeypatch, url):
    monkeypatch.setenv('SYMPORT_MGO_URL', url)
    with pytest.raises(ValueError):
        MgoClient()


def test_lab_routes_require_auth_and_stream_firmware(http_server):  # noqa: F811
    workbench, port = http_server
    agent = MockMgo()
    workbench.lab.agent = agent
    for path in ('/api/lab', '/api/lab/firmware?slot=rom&name=test.rom'):
        status, _ = _http(port, 'POST', path, {'action': 'state'})
        assert status == 403
    status, _ = _http(port, 'POST', '/api/lab', {'action': 'state'}, {'X-Symport-Token': workbench.token, 'Origin': 'https://evil.test'})
    assert status == 403
    connection = http.client.HTTPConnection('127.0.0.1', port)
    connection.request('POST', '/api/lab/firmware?slot=rom&name=test.rom', body=b'browser-stream', headers={'Content-Type': 'application/octet-stream', 'X-Symport-Token': workbench.token})
    response = connection.getresponse()
    assert response.status == 200
    assert json.loads(response.read())['sha256'] == hashlib.sha256(b'browser-stream').hexdigest()
    connection.close()
    status, raw = _http(port, 'POST', '/api/lab', {'action': 'state'}, {'X-Symport-Token': workbench.token})
    assert status == 200 and TOKEN.encode() not in raw
    for path in ['/lab.js', '/lab.css', '/nimbus.css', '/fonts/Inter.ttf', '/fonts/JetBrainsMono.ttf']:
        assert _http(port, 'GET', path)[0] == 200


def test_workbench_resolver_accepts_build_library_and_upload(http_server):  # noqa: F811
    workbench, _ = http_server
    path = workbench.repo / 'build/symport/theme/light/fixture.sis'
    path.write_bytes(sis(True))
    name, raw, hint = workbench.resolve_lab_package({'source': 'build', 'reference': 'theme:light:fixture.sis'})
    assert hint == 'theme' and name == path.name and raw == path.read_bytes()
    draft = workbench.library.import_package(name, base64.b64encode(raw).decode())
    published = workbench.library.publish(draft['id'], True)
    assert workbench.resolve_lab_package({'source': 'library', 'reference': published['id']})[1] == raw
    assert workbench.resolve_lab_package({'source': 'upload', 'name': name, 'content': base64.b64encode(raw).decode()})[1] == raw
    with pytest.raises(ValueError):
        workbench.resolve_lab_package({'source': 'catalog', 'reference': 'manual-invalid'})


def test_invalid_package_does_not_capture_previous_application(setup):
    lab, agent, _ = setup
    run(lab)
    count = sum(path.startswith('/v1/screenshot') for _, path, _ in agent.calls)
    lab.resolver = lambda data: ('invalid.sis', b'corrupt', 'app')
    report = run(lab)
    assert report['status'] == 'failed' and not report['screenshots']
    assert sum(path.startswith('/v1/screenshot') for _, path, _ in agent.calls) == count
    with pytest.raises(ValueError):
        lab.execute({'action': 'shot', 'id': report['id']})


def test_stop_racing_slow_start_does_not_leave_instance_running(setup):
    lab, agent, _ = setup
    entered, resume = threading.Event(), threading.Event()
    original = agent.request

    def delayed(method, path, body=None, **kwargs):
        if method == 'POST' and path == '/agent/instance':
            entered.set()
            assert resume.wait(3)
        return original(method, path, body, **kwargs)

    agent.request = delayed
    report = lab.execute({'action': 'start', 'code': 'mock-device'})
    assert entered.wait(3)
    lab.execute({'action': 'stop'})
    resume.set()
    result = wait(lab, report)
    assert result['status'] == 'failed' and not agent.running
    assert not result['screenshots']


def test_unavailable_screen_preserves_user_observation(setup):
    lab, agent, _ = setup
    report = run(lab, theme=True)
    agent.running = False
    result = lab.execute({'action': 'observe', 'id': report['id'], 'step': 'applied', 'result': 'unsupported'})
    assert result['status'] == 'unsupported'
    saved = lab.report(report['id'])
    assert saved['observations'][0]['result'] == 'unsupported'
    assert 'surface' in saved['screen_reason']
