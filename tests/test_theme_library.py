import base64

import pytest

from symport.library import ThemeLibrary
from symport.phone.files import MountedVolumes
from symport.sis import writer
from tests.test_sis import pkg


def test_import_publish_download_and_transfer(tmp_path):
    library = ThemeLibrary(tmp_path)
    raw = writer.build(pkg())
    draft = library.import_package('clear.sis', base64.b64encode(raw).decode())
    assert library.list() == []
    with pytest.raises(ValueError):
        library.download(draft['id'])
    with pytest.raises(ValueError):
        library.publish(draft['id'], False)
    library.publish(draft['id'], True)
    assert len(library.list()) == 1
    name, data = library.download(draft['id'])
    assert name == 'clear.sis' and data == raw
    phone = tmp_path / 'phone'
    phone.mkdir()
    result = MountedVolumes({'usb': str(phone)}).execute({
        'action': 'transfer', 'device': 'usb', 'path': name, 'confirm': True,
        'content': base64.b64encode(data).decode()})
    assert result['status'] == 'transferred-not-installed'
    assert (phone / name).read_bytes() == raw
    (library.root / (draft['id'] + '.sis')).write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        library.download(draft['id'])


def test_invalid_library_import(tmp_path):
    library = ThemeLibrary(tmp_path)
    for name in ('../../secret.sis', 'file.zip', 'bad\n.sis'):
        with pytest.raises(ValueError):
            library.import_package(name, 'aW52YWxpZA==')
    with pytest.raises(ValueError):
        library.import_package('bad.sis', 'aW52YWxpZA==')
