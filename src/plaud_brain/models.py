"""Internal data models shared across sources, AI, and sinks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class RawRecording:
    """A recording discovered by a source, before AI processing.

    ``uid`` is a stable, source-scoped identifier used for de-duplication:
    the PLAUD file id for cloud recordings, or a content/metadata hash for
    USB files. The pipeline guarantees a local ``audio_path`` exists before
    handing the recording to the AI step (downloading from ``remote_url`` if
    necessary).
    """

    uid: str
    title: str
    source: str  # "cloud" | "usb"
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    duration_ms: int = 0
    audio_path: Path | None = None
    remote_url: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def duration_display(self) -> str:
        total = self.duration_ms // 1000
        minutes, seconds = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


@dataclass(slots=True)
class ProcessedContent:
    """Output of the AI step: a transcript and a summary, both markdown."""

    transcript: str
    summary: str
    language: str = ""
    model: str = ""
