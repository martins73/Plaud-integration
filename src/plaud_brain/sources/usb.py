"""USB source: scans a mounted PLAUD_NOTE device for raw audio files.

When you enable "Access via USB" in the PLAUD app and plug the device in, it
mounts as a disk containing NOTES/ and CALLS/ folders of audio files. This
source treats those files as recordings. Because USB files have no cloud id,
the uid is derived from a fast content fingerprint (size + head/tail bytes)
so the same file is recognized across syncs even if copied or renamed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from plaud_brain.config import Config
from plaud_brain.models import RawRecording

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".opus", ".asr", ".aac", ".flac", ".ogg"}


def fingerprint(path: Path, *, chunk: int = 65536) -> str:
    """A cheap, stable id for a file: size + first/last chunk hashed.

    Avoids reading whole (potentially large) audio files while still being
    robust to renames and reliable for de-duplication.
    """
    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(chunk))
        if size > chunk:
            f.seek(max(0, size - chunk))
            h.update(f.read(chunk))
    return h.hexdigest()[:16]


class UsbSource:
    name = "usb"

    def __init__(self, config: Config) -> None:
        self._cfg = config.usb

    def iter_recordings(self) -> Iterable[RawRecording]:
        if not self._cfg.enabled:
            return
        root = Path(self._cfg.mount_path).expanduser()
        if not root.exists():
            raise FileNotFoundError(
                f"USB mount path not found: {root}. Plug in the device with "
                "'Access via USB' enabled, or update [usb].mount_path."
            )
        for folder in self._cfg.folders:
            base = root / folder
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
                    yield self._to_recording(path)

    def ensure_local_audio(self, rec: RawRecording, cache_dir: Path) -> Path:
        # USB files are already local; nothing to download.
        if rec.audio_path is None:
            raise ValueError(f"USB recording {rec.uid} has no audio path")
        return rec.audio_path

    @staticmethod
    def _to_recording(path: Path) -> RawRecording:
        stat = path.stat()
        created = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        return RawRecording(
            uid=f"usb:{fingerprint(path)}",
            title=path.stem,
            source="usb",
            created_at=created,
            duration_ms=0,  # unknown without decoding; Gemini still transcribes fine
            audio_path=path,
            extra={"original_path": str(path)},
        )
