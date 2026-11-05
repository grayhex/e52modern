"""Offline actual-FFmpeg smoke inside the image, with no phone or user volume."""
import io
import json
import math
import struct
import tempfile
import wave
from pathlib import Path

from symport.audio.studio import RingtoneStudio
from symport.phone.files import MountedVolumes
from symport.phone.media_downloads import MediaDownloads
from symport.phone.service import DeviceManager

with tempfile.TemporaryDirectory(prefix='symport-audio-container-') as temporary:
    root = Path(temporary)
    card = root / 'card'
    card.mkdir()
    devices = DeviceManager(root, MountedVolumes({'fixture': str(card)}))
    studio = RingtoneStudio(root, devices, MediaDownloads(root, devices))
    data = io.BytesIO()
    with wave.open(data, 'wb') as sound:
        sound.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
        sound.writeframes(b''.join(struct.pack('<hh', int(6000 * math.sin(i * math.tau * 440/44100)), int(4000 * math.sin(i * math.tau * 660/44100))) for i in range(44100)))
    raw = data.getvalue()
    source = studio.create(io.BytesIO(raw), len(raw))
    output = studio.export(source['id'], {'start': .1, 'end': .9, 'mono': True, 'normalize': True, 'sample_rate':22050})
    assert output['channels'] == 1 and output['sample_rate'] == 22050
    assert .7 < output['duration'] < 1
    studio.execute({'action':'transfer', 'id':source['id'], 'version':output['version'], 'device':'fixture', 'path':'', 'confirm':True})
    assert next(card.glob('*.mp3')).read_bytes() == studio.read(source['id'], output['version'])[0]
    studio.execute({'action':'delete', 'id':source['id']})
    assert not list(studio.root.iterdir())
    studio.closed.set()
    print(json.dumps({'ffmpeg':'passed','stereo_input':True,'normalized_mono_mp3':'passed','sample_rate':22050,'transfer_bytes':'matched','cleanup':'passed','phone':'not-used'}))
