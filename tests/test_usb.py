import pytest

from plaud_brain.config import Config, UsbConfig
from plaud_brain.sources.usb import UsbSource, fingerprint


def _make_device(tmp_path):
    root = tmp_path / "PLAUD_NOTE"
    (root / "NOTES").mkdir(parents=True)
    (root / "CALLS").mkdir(parents=True)
    (root / "NOTES" / "rec1.mp3").write_bytes(b"audio-one-content")
    (root / "CALLS" / "call1.wav").write_bytes(b"audio-two-content")
    (root / "NOTES" / "notes.txt").write_text("ignore me")
    return root


def test_iter_recordings_finds_audio(tmp_path):
    root = _make_device(tmp_path)
    cfg = Config(usb=UsbConfig(mount_path=str(root)))
    recs = list(UsbSource(cfg).iter_recordings())
    titles = {r.title for r in recs}
    assert titles == {"rec1", "call1"}
    assert all(r.uid.startswith("usb:") for r in recs)
    assert all(r.audio_path is not None for r in recs)


def test_disabled_when_no_mount_path():
    cfg = Config(usb=UsbConfig(mount_path=""))
    assert list(UsbSource(cfg).iter_recordings()) == []


def test_missing_mount_path_raises(tmp_path):
    cfg = Config(usb=UsbConfig(mount_path=str(tmp_path / "absent")))
    with pytest.raises(FileNotFoundError):
        list(UsbSource(cfg).iter_recordings())


def test_fingerprint_stable_and_distinct(tmp_path):
    a = tmp_path / "a.mp3"
    b = tmp_path / "b.mp3"
    a.write_bytes(b"same")
    b.write_bytes(b"different content here")
    assert fingerprint(a) == fingerprint(a)
    assert fingerprint(a) != fingerprint(b)


def test_ensure_local_audio_returns_existing(tmp_path):
    root = _make_device(tmp_path)
    cfg = Config(usb=UsbConfig(mount_path=str(root)))
    source = UsbSource(cfg)
    rec = next(iter(source.iter_recordings()))
    assert source.ensure_local_audio(rec, tmp_path / "cache") == rec.audio_path
