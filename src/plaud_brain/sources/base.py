"""The AudioSource protocol implemented by the cloud and USB sources."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from plaud_brain.models import RawRecording


@runtime_checkable
class AudioSource(Protocol):
    """A place recordings can be discovered and fetched from."""

    name: str

    def iter_recordings(self) -> Iterable[RawRecording]:
        """Yield recordings available from this source (newest first)."""
        ...

    def ensure_local_audio(self, rec: RawRecording, cache_dir: Path) -> Path:
        """Return a local path to the recording's audio, downloading if needed."""
        ...
