"""Independent SDK signature, tamper detection, fail-closed workflow and reversible staging."""
from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from symport.inspector import Inspector
from symport.inspector.service import diagnose
from symport.inspector.signatures import inspect_signatures
from symport.jailbreak import JailbreakManager
from symport.jailbreak.service import inventory
from symport.lab import EmulatorLab
from symport.phone.files import MountedVolumes
from symport.phone.service import DeviceManager
from symport.sis import fields as f
from symport.sis.reader import _decompress
from tests.lab_fixture import MockMgo, sis
from tests.test_web import _http, http_server, repo  # noqa: F401

FIXTURES = Path(__file__).parent/'fixtures'


def archive_bytes(unsafe=False):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        z.writestr('Norton-test.sis', sis())
        z.writestr('FP2 9.3.rmp', '; TEST DATA, NOT A WORKING PATCH')
        z.writestr('Nokia 5800.rmp', '; Wrong target')
        z.writestr('shared.key', 'PRIVATE TEST MATERIAL MUST NOT BE SAVED')
        if unsafe:
            z.writestr('../outside.exe', b'not executable')
    return buffer.getvalue()


@pytest.fixture
def security(tmp_path):
    volume = tmp_path/'phone'
    volume.mkdir()
    (volume/'existing.txt').write_text('original data')
    devices = DeviceManager(tmp_path, MountedVolumes({'card': volume}))
    resolver = lambda data: ('probe.sis', (FIXTURES/'sdk_probe_package_signed.sis').read_bytes(), 'app')  # noqa: E731
    lab = EmulatorLab(tmp_path, resolver, devices, MockMgo())
    return Inspector(tmp_path, resolver, devices, lab), JailbreakManager(tmp_path, devices), volume


def plan(manager, **kwargs):
    a = manager.execute({'action':'import', 'name':'fixture.zip', 'content':base64.b64encode(archive_bytes()).decode()})
    files = [e['sha256'] for e in a['entries'] if e['name']=='Norton-test.sis']
    return manager.execute(dict(action='plan', archive=a['id'], method='norton', device='card', model='Nokia E52', rm='RM-469', firmware='unknown', symbian='9.3', files=files, **kwargs))


def test_real_sdk_signature_and_expiration_are_separate():
    raw = (FIXTURES/'sdk_probe_package_signed.sis').read_bytes()
    result = inspect_signatures(raw, datetime(2050,1,1,tzinfo=UTC))
    assert result['status']=='valid' and result['trust']=='unknown'
    assert result['chains'][0]['certificates'][0]['subject']=='CN=SymPort test only'
    assert result['chains'][0]['certificates'][0]['validity']=='expired'
    assert result['chains'][0]['signatures'][0]['legacy_sha1']
    assert inspect_signatures((FIXTURES/'sdk_probe_package.sis').read_bytes())['status']=='unsigned'


def test_mathematical_tamper_even_with_correct_sis_crc():
    original = (FIXTURES/'sdk_probe_package_signed.sis').read_bytes()
    outer = f.Cursor(original,16)
    _, contents, _ = outer.field(f.T_CONTENTS)
    c = f.Cursor(contents)
    c.field()
    c.field()
    _, compressed, _ = c.field(f.T_COMPRESSED)
    _, _, data_raw = c.field(f.T_DATA)
    ctrl = _decompress(compressed)
    from symport.sis.reader import inspect
    vendor = inspect(original)['package']['vendor_unique_name']
    needle = vendor.encode('utf-16-le')
    assert needle in ctrl
    tampered = ctrl.replace(needle,('X'+vendor[1:]).encode('utf-16-le'),1)
    new_comp = f.compressed_raw(tampered)
    rebuilt = original[:16]+f.field(f.T_CONTENTS,f.field(f.T_CONTROLLER_CHECKSUM,f.u16(f.crc16(new_comp)))+f.field(f.T_DATA_CHECKSUM,f.u16(f.crc16(data_raw)))+new_comp+data_raw)
    from symport.catalog.packages import validate_package
    validate_package('tampered.sis',rebuilt)
    assert inspect_signatures(rebuilt)['status']=='invalid'


def test_inspection_report_diagnosis_and_no_implicit_transfer(security):
    inspector, _, volume = security
    report = inspector.execute({'action':'analyze','source':'upload','at':'2050-01-01','target':{'model':'Nokia E52','firmware':'unknown','os':'9.3'}})
    assert report['signatures']['status']=='valid' and 'expired-certificate' in report['issues']
    assert report['physical_device']=='not-tested' and report['compatibility']=='unknown'
    assert report['binaries'][0]['cpu']=='armv5'
    assert report['dependencies'] is not None and report['sha256']
    assert sorted(p.name for p in volume.iterdir())==['existing.txt']
    with pytest.raises(ValueError,match='acknowledgement'):
        inspector.execute({'action':'transfer','id':report['id'],'device':'card','path':'probe.sis','confirm':True})
    result = inspector.execute({'action':'transfer','id':report['id'],'device':'card','path':'probe.sis','confirm':True,'ack_unverified':True})
    assert result['status']=='transferred-not-installed'
    assert (volume/'probe.sis').read_bytes()==(FIXTURES/'sdk_probe_package_signed.sis').read_bytes()
    assert diagnose('Срок действия сертификата истек')['code']=='expired-certificate'
    assert diagnose('Missing capabilities')['code']=='missing-capabilities'
    assert diagnose('Random crash')['code']=='unknown'


def test_profile_must_match_exact_firmware(security):
    inspector,_,_=security
    with pytest.raises(ValueError,match='exact firmware'):
        inspector.execute({'action':'analyze','target':{'model':'Nokia E52','firmware':'other'},'firmware_profile':{'schema':1,'device':'nokia-e52','firmware_version':'v1','dlls':{}}})


def test_inventory_excludes_private_keys_and_wrong_model():
    result = inventory(archive_bytes(),'fixture.zip')
    assert next(e for e in result['entries'] if e['name']=='shared.key')=={'name':'shared.key','size':39,'excluded':'private-key-material'}
    assert next(e for e in result['entries'] if '5800' in e['name'])['e52']=='incompatible-target-claim'
    with pytest.raises(ValueError,match='Unsafe'):
        inventory(archive_bytes(True),'bad.zip')


def test_backup_stage_rollback_and_conflict_protection(security):
    _,manager,volume=security
    run=plan(manager)
    assert run['dry_run'] and run['system_automation']=='blocked'
    with pytest.raises(ValueError,match='Backup'):
        manager.execute({'action':'stage','id':run['id'],'confirm':True,'ack_risk':True})
    for action in ('install','patch','system-write','restore-system'):
        with pytest.raises(ValueError,match='blocked'):
            manager.execute({'action':action,'id':run['id'],'confirm':True,'confirm_system':True})
    backup=manager.execute({'action':'backup','id':run['id'],'confirm':True})
    assert backup['backup']['complete_phone_backup'] is False
    exported=manager.execute({'action':'backup-export','id':run['id']})
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported['content']))) as z:
        assert z.read('existing.txt')==b'original data'
    staged=manager.execute({'action':'stage','id':run['id'],'confirm':True,'ack_risk':True})
    assert staged['installation']=='not-tested' and staged['staged']
    path=volume/staged['staged'][0]['path']
    original=path.read_bytes()
    path.write_bytes(b'changed on phone')
    rollback=manager.execute({'action':'rollback','id':run['id'],'confirm':True})
    assert rollback['rollback']['conflicts'] and path.read_bytes()==b'changed on phone'
    path.write_bytes(original)
    rollback=manager.execute({'action':'rollback','id':run['id'],'confirm':True})
    assert not path.exists() and rollback['rollback']['system_restored'] is False
    assert (volume/'existing.txt').read_text()=='original data'
    assert not any(b'PRIVATE TEST' in p.read_bytes() for p in (manager.root/'files').iterdir())


def test_manual_steps_need_separate_confirmation_and_probe_is_nonexecutable(security):
    _,manager,_=security
    run=plan(manager)
    with pytest.raises(ValueError,match='Separate'):
        manager.execute({'action':'manual-step','id':run['id'],'step':'apply-patch','result':'pass','confirm':True})
    manager.execute({'action':'backup','id':run['id'],'confirm':True})
    result=manager.execute({'action':'manual-step','id':run['id'],'step':'apply-patch','result':'pass','confirm':True,'confirm_system':True})
    assert result['events'][-1]['status']=='manual-observation' and result['installation']=='not-tested'
    probe=manager.execute({'action':'probe','id':run['id']})
    from symport.sis.reader import inspect
    package=inspect(base64.b64decode(probe['content']))
    assert all(f['target'].endswith('.txt') for f in package['files'])


def test_api_auth_and_invalid_sources(http_server):  # noqa: F811
    state,port=http_server
    for path in ['/api/inspector','/api/jailbreak']:
        assert _http(port,'POST',path,{'action':'state'})[0]==403
        assert _http(port,'POST',path,{'action':'state'},{'X-Symport-Token':state.token,'Origin':'https://evil.test'})[0]==403
    assert _http(port,'POST','/api/jailbreak',{'action':'state'},{'X-Symport-Token':state.token})[0]==200
    for path in ['/preferences.js','/translations.json','/preferences.css','/inspector.js']:
        assert _http(port,'GET',path)[0]==200


def test_no_embedded_private_keys_or_unverified_archive_executables():
    root=Path(__file__).resolve().parents[1]
    import subprocess
    paths=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines()
    assert not any(p.lower().endswith(('.key','.pem','.p12','.pfx')) for p in paths)
    assert not any('norton' in p.lower() and p.endswith(('.sis','.sisx','.exe')) for p in paths)
    catalog=json.loads((root/'symport/web_assets/translations.json').read_text())
    assert catalog['en']['Контакты']=='Contacts'


def test_optional_crc_is_unknown_not_fabricated_valid():
    raw=(FIXTURES/'sdk_probe_package.sis').read_bytes()
    _,contents,_=f.Cursor(raw,16).field(f.T_CONTENTS)
    c=f.Cursor(contents)
    c.field()
    c.field()
    remaining=contents[c.pos:]
    without_crc=raw[:16]+f.field(f.T_CONTENTS,remaining)
    from symport.catalog.packages import validate_package
    result=validate_package('no-crc.sis',without_crc)
    assert result['checksums']['controller_crc_ok'] is None and result['checksums']['data_crc_ok'] is None
    assert result['checksums']['uid_checksum_ok'] is True


def test_original_backup_is_not_replaced_and_wrong_target_is_blocked(security):
    _,manager,volume=security
    run=plan(manager)
    before=manager.execute({'action':'backup','id':run['id'],'confirm':True})['backup']['sha256']
    (volume/'existing.txt').write_text('after manual change')
    after=manager.execute({'action':'backup','id':run['id'],'confirm':True})['backup']['sha256']
    assert before==after
    a=manager.execute({'action':'state'})['archives'][0]
    wrong=next(e['sha256'] for e in a['entries'] if '5800' in e['name'])
    with pytest.raises(ValueError):
        manager.execute({'action':'plan','archive':a['id'],'method':'norton','model':'E52','firmware':'unknown','files':[wrong]})


def test_bad_zip_returns_a_controlled_error(security):
    _,manager,_=security
    with pytest.raises(ValueError,match='ZIP'):
        manager.execute({'action':'import','content':base64.b64encode(b'invalid ZIP').decode()})


def test_inspector_preserves_theme_scenario_in_emulator(security):
    import time
    inspector,_,_=security
    inspector.resolver=lambda data: ('theme.sis',sis(True),'theme')
    report=inspector.execute({'action':'analyze','source':'library'})
    assert report['kind']=='theme'
    started=inspector.execute({'action':'emulate','id':report['id'],'code':'mock-device','confirm':True})
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        evidence=inspector.lab.report(started['id'])
        if not evidence['running']:
            break
        time.sleep(.01)
    assert evidence['kind']=='theme' and evidence['install']=='installed' and evidence['launch']=='unsupported'
    assert not any(path.endswith('/launch') for _,path,_ in inspector.lab.agent.calls)
