"""Media to Nokia (#41): sandboxed conversion with limits, honest presets, exported ≠ transferred ≠ played."""
import base64
import io
import json
import shutil
import subprocess
import time

import pytest

from symport.phone import DeviceManager
from symport.phone.registry import registry
from symport.revive import ReviveService, media_prep
from tests.test_revive import b64, phone
from tests.test_safety import SafetyPhone

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")


def make_video(tmp_path, seconds=1, size="640x480"):
    path = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size={size}:rate=25",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path.read_bytes()


def make_audio(tmp_path):
    path = tmp_path / "src.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-metadata", "title=Secret Title", str(path)], check=True)
    return path.read_bytes()


def make_image(width=800, height=600):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def svc(tmp_path):
    transport = SafetyPhone()
    s = ReviveService(tmp_path, DeviceManager(tmp_path, transport))
    s.transport = transport
    return s


def upload(svc, raw, name="clip.bin"):
    return svc.execute({"action": "media-upload", "name": name, "content": b64(raw)})


def finish(svc, source, preset, model="nokia-e52", **kw):
    job = svc.execute({"action": "media-convert", "source": source["id"], "model": model, "preset": preset, **kw})
    for _ in range(600):
        view = svc.execute({"action": "media-job", "job": job["id"]})
        if view["state"] in ("done", "failed"):
            return view
        time.sleep(0.1)
    raise AssertionError("conversion did not finish")


def probe(path_bytes, tmp_path, name):
    path = tmp_path / name
    path.write_bytes(path_bytes)
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height:format=format_name:format_tags", "-of", "json", str(path)],
                         capture_output=True, check=True)
    return json.loads(out.stdout)


def test_presets_are_theoretical_for_every_model_and_never_hardware_verified(svc):
    for model in media_prep.TARGETS:
        result = svc.execute({"action": "media-presets", "model": model})
        assert result["screen"] and "check the result on the phone" in result["statement"]
        for kind in ("video", "audio", "image"):
            assert result["presets"][kind]
            assert all(p["hardware"] == "not-tested" and p["basis"].startswith("theoretical") for p in result["presets"][kind])
    with pytest.raises(ValueError, match="supported phone model"):
        svc.execute({"action": "media-presets", "model": "nokia-n95-family"})


def test_video_is_converted_with_aspect_kept_and_reported_honestly(svc, tmp_path):
    source = upload(svc, make_video(tmp_path))
    assert source["kind"] == "video" and source["video"]["width"] == 640
    view = finish(svc, source, "mp4-qvga-h264")
    assert view["state"] == "done" and view["output"]["size"] > 0 and view["hardware"] == "not-tested" and view["preview"]
    exported = svc.execute({"action": "media-export", "job": view["id"]})
    raw = base64.b64decode(exported["content"])
    meta = probe(raw, tmp_path, "out.mp4")
    video = next(s for s in meta["streams"] if s.get("width"))
    assert (video["width"], video["height"], video["codec_name"]) == (320, 240, "h264")
    report = json.loads(base64.b64decode(exported["report"]))
    assert report["hardware"] == "not-tested" and report["outcomes"] == {"exported": True, "transferred": False, "played-on-device": "not-tested"}
    assert report["output"]["sha256"] == view["output"]["sha256"] and "not transferred and not played" in report["statement"]
    assert view["estimate_bytes"] > 0


def test_3gp_preset_and_rotation(svc, tmp_path):
    source = upload(svc, make_video(tmp_path))
    view = finish(svc, source, "3gp-qcif-mpeg4", rotate=90)
    assert view["state"] == "done"
    raw = base64.b64decode(svc.execute({"action": "media-export", "job": view["id"]})["content"])
    video = next(s for s in probe(raw, tmp_path, "out.3gp")["streams"] if s.get("width"))
    assert (video["width"], video["height"]) == (176, 144)
    with pytest.raises(ValueError, match="Rotation"):
        svc.execute({"action": "media-convert", "source": source["id"], "model": "nokia-e52", "preset": "3gp-qcif-mpeg4", "rotate": 45})


def test_audio_conversion_strips_metadata(svc, tmp_path):
    source = upload(svc, make_audio(tmp_path))
    assert source["kind"] == "audio"
    view = finish(svc, source, "mp3-128")
    raw = base64.b64decode(svc.execute({"action": "media-export", "job": view["id"]})["content"])
    meta = probe(raw, tmp_path, "out.mp3")
    assert meta["streams"][0]["codec_name"] == "mp3" and "Secret Title" not in json.dumps(meta)
    assert view["output"]["name"] == "clip.mp3" and view["preview"] is None


def test_pictures_are_cropped_or_fitted_to_the_model_screen(svc):
    from PIL import Image
    source = upload(svc, make_image(), "wall.png")
    assert source["kind"] == "image"
    wall = finish(svc, source, "wallpaper-jpeg", model="nokia-e52")
    out = Image.open(io.BytesIO(base64.b64decode(svc.execute({"action": "media-export", "job": wall["id"]})["content"])))
    screen = registry()["nokia-e52"]["screen"]
    assert out.size == (screen["width"], screen["height"])
    fit = finish(svc, source, "photo-fit-png", model="nokia-n95")
    out = Image.open(io.BytesIO(base64.b64decode(svc.execute({"action": "media-export", "job": fit["id"]})["content"])))
    assert out.size[0] <= 240 and out.size[1] <= 320 and round(out.size[0] / out.size[1], 1) == round(800 / 600, 1)


def test_bad_oversized_and_overlong_inputs_are_refused(svc, tmp_path, monkeypatch):
    for junk in (b"\x00" * 4096, b"definitely not media", make_video(tmp_path)[:300]):
        with pytest.raises(ValueError):
            upload(svc, junk)
    with pytest.raises(ValueError, match="base64"):
        svc.execute({"action": "media-upload", "name": "x", "content": "***"})
    monkeypatch.setattr(media_prep, "MAX_INPUT", 1000)
    with pytest.raises(ValueError, match="between 1 byte"):
        upload(svc, make_audio(tmp_path))
    monkeypatch.setattr(media_prep, "MAX_INPUT", 48 * 1024**2)
    monkeypatch.setattr(media_prep, "MAX_DURATION", 0.5)
    with pytest.raises(ValueError, match="lasting"):
        upload(svc, make_audio(tmp_path))
    assert not [p for p in (tmp_path / "build/symport/revive/media-prep").glob("*")]


def test_kind_mismatch_unknown_model_output_limit_timeout_and_queue(svc, tmp_path, monkeypatch):
    video = upload(svc, make_video(tmp_path))
    with pytest.raises(ValueError, match="does not fit"):
        svc.execute({"action": "media-convert", "source": video["id"], "model": "nokia-e52", "preset": "mp3-128"})
    with pytest.raises(ValueError, match="supported phone model"):
        svc.execute({"action": "media-convert", "source": video["id"], "model": "nokia-e71", "preset": "mp4-qvga-h264"})
    with pytest.raises(ValueError, match="expired or is unknown"):
        svc.execute({"action": "media-convert", "source": "0" * 32, "model": "nokia-e52", "preset": "mp4-qvga-h264"})
    monkeypatch.setattr(media_prep, "MAX_OUTPUT", 1000)
    big = finish(svc, video, "mp4-qvga-h264")
    assert big["state"] == "failed" and "larger than 48 MiB" in big["error"]
    monkeypatch.setattr(media_prep, "MAX_OUTPUT", 48 * 1024**2)
    svc.media.timeout = 0.001
    slow = finish(svc, video, "mp4-qvga-h264")
    assert slow["state"] == "failed" and "timed out" in slow["error"]
    svc.media.timeout = 240
    monkeypatch.setattr(media_prep, "QUEUE_LIMIT", 0)
    with pytest.raises(ValueError, match="queue is full"):
        svc.execute({"action": "media-convert", "source": video["id"], "model": "nokia-e52", "preset": "mp4-qvga-h264"})


def test_temporary_files_expire_and_can_be_discarded(svc, tmp_path):
    source = upload(svc, make_audio(tmp_path))
    folder = tmp_path / "build/symport/revive/media-prep" / source["id"]
    assert folder.is_dir()
    svc.execute({"action": "media-discard", "id": source["id"]})
    assert not folder.exists()
    again = upload(svc, make_audio(tmp_path))
    svc.media.sources[again["id"]]["expires"] = time.monotonic() - 1
    svc.media.cleanup()
    assert not (tmp_path / "build/symport/revive/media-prep" / again["id"]).exists()
    with pytest.raises(ValueError, match="expired or is unknown"):
        svc.execute({"action": "media-convert", "source": again["id"], "model": "nokia-e52", "preset": "mp3-128"})


def ready_job(svc, tmp_path, model="nokia-e52"):
    source = upload(svc, make_audio(tmp_path), "tune.wav")
    return finish(svc, source, "mp3-64-mono", model=model)


def test_transfer_goes_through_the_safety_net_and_is_not_play_or_export(svc, tmp_path):
    job = ready_job(svc, tmp_path)
    plan = svc.execute({"action": "safety-plan", "scenario": "media", "device": "usb", "job": job["id"]})
    assert plan["folder"] == "SymPort-Media" and plan["risk"]["level"] == "low" and plan["blocking"] == []
    svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})
    done = svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    assert done["status"] == "transferred-awaiting-manual-install" and "SymPort-Media/tune.mp3" in svc.transport.files
    view = svc.execute({"action": "media-job", "job": job["id"]})
    assert view["outcomes"] == {"exported": False, "transferred": False, "played-on-device": "not-tested"}  # played/transferred are never inferred here
    with pytest.raises(ValueError, match="Confirm"):
        svc.execute({"action": "media-record", "device": "usb", "job": job["id"], "result": "pass"})
    rec = svc.execute({"action": "media-record", "device": "usb", "job": job["id"], "result": "pass", "confirm": True})
    assert rec["outcomes"]["played-on-device"] == "pass"


def test_transfer_blocks_for_no_space_other_model_and_existing_files(svc, tmp_path):
    job = ready_job(svc, tmp_path)
    svc.transport.row = phone(free=1000)
    plan = svc.execute({"action": "safety-plan", "scenario": "media", "device": "usb", "job": job["id"]})
    assert any(b["code"] == "gate-space" for b in plan["blocking"])
    svc.execute({"action": "safety-snapshot", "plan": plan["id"], "confirm": True})
    with pytest.raises(ValueError, match="gate-space"):
        svc.execute({"action": "safety-apply", "plan": plan["id"], "confirm": True})
    svc.transport.row = phone(model="Nokia E72")
    other = svc.execute({"action": "safety-plan", "scenario": "media", "device": "usb", "job": job["id"]})
    assert any(b["code"] == "gate-preset-for-other-model" for b in other["blocking"])
    svc.transport.row = phone()
    svc.transport.files["SymPort-Media/tune.mp3"] = b"my own file"
    conflict = svc.execute({"action": "safety-plan", "scenario": "media", "device": "usb", "job": job["id"]})
    assert conflict["dry_run"]["conflicts"] == ["SymPort-Media/tune.mp3"]
    assert svc.transport.files["SymPort-Media/tune.mp3"] == b"my own file"
    with pytest.raises(ValueError, match="not finished|unknown"):
        svc.execute({"action": "safety-plan", "scenario": "media", "device": "usb", "job": "0" * 32})
