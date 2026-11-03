import base64
import io
import zipfile

import pytest

from symport.phone.files import MountedVolumes


def data(content=b'test', path='ringtone.mp3', action='media-upload', **kw):
    return {'device': 'phone', 'path': path, 'action': action, 'kind': 'audio',
            'content': base64.b64encode(content).decode(), 'confirm': True, **kw}


def test_media_transfer_bytes_and_no_overwrite(tmp_path):
    transport = MountedVolumes({'phone': str(tmp_path)})
    transport.execute(data())
    assert (tmp_path / 'ringtone.mp3').read_bytes() == b'test'
    with pytest.raises(FileExistsError):
        transport.execute(data())
    with pytest.raises(ValueError):
        transport.execute(data(path='not-a-media.exe'))
    with pytest.raises(ValueError):
        transport.execute(data(confirm=False))
    transport.execute(data(path='clip.3gp', kind='video'))


def test_java_package_requires_manifest_and_is_only_staged(tmp_path):
    transport = MountedVolumes({'phone': str(tmp_path)})
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as jar:
        jar.writestr('Main.class', b'\xca\xfe\xba\xbe')
        jar.writestr('META-INF/MANIFEST.MF', 'MIDlet-Name: Test\nMIDlet-Version: 1.0\nMIDlet-Vendor: Test\nMIDlet-1: Test,,Main\n')
    result = transport.execute(data(raw.getvalue(), 'game.jar', 'software-transfer'))
    assert result['status'] == 'transferred-not-installed'
    with pytest.raises(ValueError):
        transport.execute(data(path='game.txt', action='software-transfer'))
    with pytest.raises(ValueError):
        transport.execute(data(path='CON.mp3'))


def test_video_larger_than_generic_file_limit(tmp_path):
    payload = b'x' * (9 * 1024 * 1024)
    transport = MountedVolumes({'phone': str(tmp_path)})
    transport.execute(data(payload, path='clip.mp4', kind='video'))
    assert (tmp_path / 'clip.mp4').stat().st_size == len(payload)
    with pytest.raises(ValueError):
        transport.execute(data(payload, path='generic.bin', action='upload'))
