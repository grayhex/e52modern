"""HTTP smoke for an explicitly enrolled disposable container fixture, never a phone."""
import argparse
import base64
import http.client
import io
import json
import os
import re
import wave
import zipfile
from pathlib import Path
from urllib.parse import urlencode

from PIL import Image

args = argparse.ArgumentParser()
args.add_argument('--port', type=int, default=8765)
port = args.parse_args().port
root = Path.cwd() / 'workspace/media-smoke'
assert json.loads(os.environ.get('SYMPORT_DEVICE_ROOTS', '{}')) == {'smoke': str(root)}, 'Refuse to write outside the exact disposable fixture enrollment'
root.mkdir(parents=True, exist_ok=False)
Image.new('RGB', (64, 48), '#22d3ee').save(root / 'photo.jpg')
with wave.open(str(root / 'sound.wav'), 'wb') as sound:
    sound.setnchannels(1)
    sound.setsampwidth(2)
    sound.setframerate(8000)
    sound.writeframes(bytes(16000))


def request(method, path, body=None, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
    encoded = json.dumps(body) if body is not None else None
    connection.request(method, path, encoded, headers or {})
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


status, headers, html = request('GET', '/')
assert status == 200
session = re.search(rb'name="symport-token" content="([^"]+)"', html).group(1).decode()
cookie = headers['Set-Cookie'].split(';', 1)[0]
auth = {'X-Symport-Token': session, 'Content-Type': 'application/json'}


def manager(data):
    status, _, raw = request('POST', '/api/manager', data, auth)
    assert status == 200, 'Device API request failed'
    return json.loads(raw)


device = manager({'action': 'discover'})['devices'][0]
assert device['model'] is None and device['battery'] is None and device['firmware_update']['status'] == 'unknown'
items = manager({'action': 'media-list', 'device': 'smoke'})['items']
assert {item['name'] for item in items} == {'photo.jpg', 'sound.wav'}
photo = next(i for i in items if i['name'] == 'photo.jpg')
thumbnail = manager({'action': 'media-thumbnail', 'device': 'smoke', 'path': photo['path'], 'revision': photo['revision']})
assert base64.b64decode(thumbnail['content']).startswith(b'\xff\xd8')
sound = next(i for i in items if i['name'] == 'sound.wav')
url = '/api/media/file?' + urlencode({'device': 'smoke', 'path': sound['path'], 'revision': sound['revision']})
assert request('GET', url)[0] == 403
status, range_headers, raw = request('GET', url, headers={'Cookie': cookie, 'Range': 'bytes=0-43'})
assert status == 206 and raw[:4] == b'RIFF' and len(raw) == 44
status, _, raw = request('POST', '/api/media/export', {'device': 'smoke', 'items': items}, auth)
assert status == 200
url = json.loads(raw)['url']
status, _, raw = request('GET', url, headers={'Cookie': cookie})
assert status == 200
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    assert set(archive.namelist()) == {'photo.jpg', 'sound.wav'}
    assert archive.read('sound.wav') == (root / 'sound.wav').read_bytes()
assert request('POST', '/api/manager', {'action': 'firmware-install', 'device': 'smoke', 'confirm': True}, auth)[0] == 400
history = manager({'action': 'history'})['operations']
assert any(x['action'] == 'media-export' and x['status'] == 'success' for x in history)
assert not any(x['action'] in ('media-chunk', 'media-thumbnail') for x in history)
print(json.dumps({'container': 'passed', 'filesystem_media': 2, 'thumbnail': 'jpeg',
                  'private_media_without_cookie': 403, 'range': 206, 'zip': 'byte-verified',
                  'unknown_identity_preserved': True, 'firmware_install': 'unavailable',
                  'journal': 'logical-operations-only'}))
