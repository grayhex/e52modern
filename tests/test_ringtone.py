"""Real FFmpeg decode, LUFS/export and private HTTP/DeviceManager integration."""
import io
import json
import math
import shutil
import struct
import wave

import pytest

from symport.audio.studio import RingtoneStudio
from symport.phone.files import MountedVolumes
from symport.phone.local import LocalTransports
from symport.phone.media_downloads import MediaDownloads
from symport.phone.service import DeviceManager
from tests.test_web import _http, http_server, repo  # noqa: F401


def audio_bytes(seconds=2):
    out = io.BytesIO()
    with wave.open(out,'wb') as sound:
        sound.setnchannels(2)
        sound.setsampwidth(2)
        sound.setframerate(44100)
        sound.writeframes(b''.join(struct.pack('<hh',int(4000*math.sin(i*2*math.pi*440/44100)),int(3000*math.sin(i*2*math.pi*660/44100))) for i in range(int(seconds*44100))))
    return out.getvalue()


@pytest.fixture
def studio(tmp_path):
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg is exercised by the Docker/browser CI job')
    phone = tmp_path/'phone'
    phone.mkdir()
    transport = LocalTransports(tmp_path)
    transport.files = MountedVolumes({'card':str(phone)})
    manager = DeviceManager(tmp_path,transport)
    service = RingtoneStudio(tmp_path,manager,MediaDownloads(tmp_path,manager))
    yield service,phone
    service.closed.set()


def test_real_decode_export_readback_transfer_and_cleanup(studio):
    service,phone = studio
    raw=audio_bytes()
    source=service.create(io.BytesIO(raw),len(raw))
    assert source['duration'] == 2 and source['channels'] == 2
    export=service.export(source['id'],dict(start=.2,end=1.7,normalize=True,mono=True,lufs=-16,fade_in=.1,fade_out=.2,bitrate=128,sample_rate=22050))
    assert export['channels']==1 and export['sample_rate']==22050
    assert 1.4 < export['duration'] < 1.7 and export['size'] > 1000
    mp3,mime=service.read(source['id'],export['version'])
    assert mime=='audio/mpeg' and not mp3.startswith(b'RIFF')
    request=dict(action='transfer',id=source['id'],version=export['version'],device='card',path='',confirm=True)
    service.execute(request)
    assert next(phone.glob('*.mp3')).read_bytes() == mp3
    with pytest.raises(ValueError):
        service.execute(dict(request,confirm=False))
    service.execute({'action':'delete','id':source['id']})
    assert not (service.root/source['id']).exists()


@pytest.mark.parametrize('data',[{'start':'0;touch x'}, {'end':float('nan')}, {'mono':'false'}, {'sample_rate':999999}, {'bitrate':True}, {'start':0,'end':200}, {'fade_out':999}, {'lufs':-100}])
def test_parameter_validation(data):
    with pytest.raises(ValueError):
        RingtoneStudio.options(data,300)


def test_invalid_media_cleanup_and_source_limit(studio):
    service,_=studio
    with pytest.raises(ValueError):
        service.create(io.BytesIO(b'not audio'),9)
    assert not list(service.root.iterdir())
    with pytest.raises(ValueError):
        service.create(io.BytesIO(b'abc'),64*1024**2+1)
    raw=audio_bytes(.5)
    item=service.create(io.BytesIO(raw),len(raw))
    service.items[item['id']]['expires']=0
    service.cleanup()
    assert not list(service.root.iterdir())


def test_gallery_source_uses_existing_device_chunks(studio):
    service,phone=studio
    (phone/'audio.wav').write_bytes(audio_bytes(.5))
    listing=service.devices.execute({'action':'media-list','device':'card','path':''})
    source=service.execute(dict(action='gallery',device='card',path='audio.wav',revision=listing['items'][0]['revision']))
    assert source['duration']==.5


def test_audio_http_requires_private_session_and_checks_ranges(http_server):  # noqa: F811
    import http.client
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg unavailable')
    state,port=http_server
    assert _http(port,'POST','/api/ringtone',{'action':'delete'})[0]==403
    connection=http.client.HTTPConnection('127.0.0.1',port)
    raw=audio_bytes(.5)
    connection.request('POST','/api/ringtone/upload',raw,{'Content-Type':'application/octet-stream','X-Symport-Token':state.token})
    response=connection.getresponse()
    assert response.status==200
    source=json.loads(response.read())
    connection.close()
    assert _http(port,'GET',source['preview'])[0]==403
    headers={'Cookie':'symport_media='+state.token,'Range':'bytes=0-43'}
    status,body=_http(port,'GET',source['preview'],headers=headers)
    assert status==206 and len(body)==44 and body[:4]==b'RIFF'
    assert _http(port,'GET',source['preview'],headers=dict(headers,**{'Sec-Fetch-Site':'cross-site'}))[0]==403


@pytest.mark.parametrize('suffix,codec',[('m4a','aac'),('mp4','aac'),('flac','flac')])
def test_real_supported_input_containers(studio,suffix,codec):
    service,_=studio
    raw=audio_bytes(.5)
    original=service.root/'fixture.wav'
    original.write_bytes(raw)
    converted=service.root/('fixture.'+suffix)
    service.ffmpeg(original,converted,extra=('-c:a',codec))
    raw=converted.read_bytes()
    source=service.create(io.BytesIO(raw),len(raw))
    assert .4 < source['duration'] < .7


def test_playlist_and_invalid_filter_are_rejected(studio):
    service,_=studio
    playlist=b'#EXTM3U\n#EXTINF:1,private\nfile:///etc/passwd\n'
    with pytest.raises(ValueError):
        service.create(io.BytesIO(playlist),len(playlist))
    with pytest.raises(ValueError):
        service.options({'fade_in':'afade;evil'},2)
