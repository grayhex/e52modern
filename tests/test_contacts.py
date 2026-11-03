"""Contact interchange and transport tests; fixtures are synthetic, not handset evidence."""
import base64
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from symport.phone.contacts import normalize, parse_export, vcards
from symport.phone.files import MountedVolumes
from symport.phone.gammu_contacts import import_contacts
from tests.test_web import _http, http_server, repo  # noqa: F401

CONTACT = {'name': 'Анна Иванова', 'given': 'Анна', 'family': 'Иванова',
           'phones': ['+7 (999) 123-45-67', '+7 999 7654321'], 'emails': ['anna@example.test']}


def encoded(text):
    return base64.b64encode(text.encode('utf-8')).decode()


def test_google_csv_old_and_current_headers_roundtrip():
    for first, last in [('Given Name', 'Family Name'), ('First Name', 'Last Name')]:
        csv = f'\ufeffName,{first},{last},Phone 1 - Value,Phone 2 - Value,E-mail 1 - Value\r\n"Анна Иванова",Анна,Иванова,+7 (999) 123-45-67,+7 999 7654321,anna@example.test\r\n'
        result = parse_export('Google.csv', encoded(csv))
        assert result['contacts'] == [CONTACT]
        restored = parse_export('contacts.vcf', encoded(''.join(vcards(result['contacts']))))
        assert restored['contacts'] == [CONTACT]


def test_apple_vcard_folded_lines_multicard_escaping_and_duplicates():
    raw = 'BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Анна Ива\r\n нова\r\nN:Иванова;Анна;;;\r\nTEL;TYPE=CELL:+79991234567\r\nEMAIL:anna@example.test\r\nEND:VCARD\r\n'
    result = parse_export('iCloud.vcf', encoded(raw + raw))
    assert result['contacts'][0]['name'] == 'Анна Иванова'
    assert result['duplicates'] == 1
    escaped = dict(CONTACT, name='Ann; Hello, World \\ Name')
    assert parse_export('file.vcf', encoded(''.join(vcards([escaped]))))['contacts'][0] == escaped


@pytest.mark.parametrize('name,raw', [('unknown.csv', 'Wrong,Columns\na,b'),
                                      ('bad.vcf', 'BEGIN:VCARD\nFN:bad'),
                                      ('empty.csv', 'Name\n'), ('file.exe', 'data')])
def test_invalid_exports_are_rejected(name, raw):
    with pytest.raises(ValueError):
        parse_export(name, encoded(raw))


def test_no_vcard_field_injection_and_type_validation():
    with pytest.raises(ValueError):
        vcards([dict(CONTACT, name='User\r\nTEL:+123')])
    with pytest.raises(ValueError):
        normalize([dict(CONTACT, phones='not-a-list')])


def test_contact_stage_creates_individual_vcards_without_claiming_import(tmp_path):
    volume = MountedVolumes({'phone': str(tmp_path)})
    data = {'device': 'phone', 'path': '', 'action': 'contacts-stage', 'contacts': [CONTACT]}
    with pytest.raises(ValueError):
        volume.execute(data)
    result = volume.execute(dict(data, confirm=True))
    assert result['status'] == 'vcards-transferred-not-imported'
    card = tmp_path / result['folder'] / 'contact-0001.vcf'
    assert parse_export(card.name, base64.b64encode(card.read_bytes()).decode())['contacts'] == [CONTACT]


def test_gammu_checks_existing_contacts_and_verifies_after_add(monkeypatch):
    snapshots = iter([[], [CONTACT]])
    monkeypatch.setattr('symport.phone.gammu_contacts.read', lambda config: next(snapshots))
    commands = []
    def run(config, args):
        commands.append(args)
        assert 'Анна' in Path(args[1]).read_text()
    monkeypatch.setattr('symport.phone.gammu_contacts._run', run)
    result = import_contacts('/private/config', [CONTACT], True)
    assert result['status'] == 'verified-in-phonebook' and result['verified'] == 1
    assert commands[0][0] == 'addnew' and commands[0][-2:] == ['-memory', 'ME']
    assert not Path(commands[0][1]).exists()


def test_gammu_no_false_success_and_no_duplicate_reimport(monkeypatch):
    monkeypatch.setattr('symport.phone.gammu_contacts.read', lambda config: [CONTACT])
    monkeypatch.setattr('symport.phone.gammu_contacts._run', lambda *a: pytest.fail('Unexpected write'))
    assert import_contacts('cfg', [CONTACT], True)['status'] == 'already-present'
    monkeypatch.setattr('symport.phone.gammu_contacts.read', lambda config: [])
    monkeypatch.setattr('symport.phone.gammu_contacts._run', lambda *a: None)
    assert import_contacts('cfg', [CONTACT], True)['status'] == 'partial-or-unverified'
    with pytest.raises(ValueError):
        import_contacts('cfg', [CONTACT], False)


def test_gammu_failure_does_not_expose_phonebook(monkeypatch):
    from symport.phone.gammu_contacts import read
    monkeypatch.setattr('symport.phone.gammu_contacts.subprocess.run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, b'private name', b'private number'))
    with pytest.raises(ValueError) as error:
        read('cfg')
    assert 'private' not in str(error.value)


def test_authenticated_contact_preview_and_export(http_server):  # noqa: F811
    state, port = http_server
    payload = {'action': 'preview', 'name': 'test.csv', 'content': encoded('Name,Phone 1 - Value\nTest,+123\n')}
    assert _http(port, 'POST', '/api/contacts', payload)[0] == 403
    headers = {'X-Symport-Token': state.token}
    code, body = _http(port, 'POST', '/api/contacts', payload, headers)
    contacts = json.loads(body)['contacts']
    assert code == 200 and contacts[0]['phones'] == ['+123']
    code, body = _http(port, 'POST', '/api/contacts', {'action': 'export', 'contacts': contacts}, headers)
    assert code == 200
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(json.loads(body)['zip']))) as archive:
        assert archive.namelist() == ['contact-0001.vcf']
    assert not (state.repo / 'build' / 'symport' / 'device-manager' / 'operations.jsonl').exists()


def test_gammu_vcard21_quoted_printable():
    raw = ('BEGIN:VCARD\r\nVERSION:2.1\r\n'
           'FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:=D0=90=D0=BD=D0=BD=D0=B0\r\n'
           'N;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:;=D0=90=D0=BD=D0=BD=D0=B0;;;\r\n'
           'TEL;PREF:+79991234567\r\nEND:VCARD\r\n')
    contact = parse_export('gammu.vcf', encoded(raw))['contacts'][0]
    assert contact['name'] == 'Анна' and contact['given'] == 'Анна'


def test_edited_duplicate_contacts_are_written_only_once(monkeypatch):
    snapshots = iter([[], [CONTACT]])
    monkeypatch.setattr('symport.phone.gammu_contacts.read', lambda config: next(snapshots))
    monkeypatch.setattr('symport.phone.gammu_contacts._run', lambda config, args: None)
    result = import_contacts('cfg', [CONTACT, CONTACT], True)
    assert result['verified'] == 1 and result['skipped'] == 1


def test_empty_gammu_export_is_not_claimed_as_supported_empty_phonebook(monkeypatch):
    from symport.phone.gammu_contacts import read
    monkeypatch.setattr('symport.phone.gammu_contacts._run', lambda config, args:
                        Path(args[1]).write_bytes(b''))
    with pytest.raises(ValueError, match='пустой экспорт'):
        read('cfg')
