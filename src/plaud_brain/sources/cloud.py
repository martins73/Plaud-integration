"""Cloud source: pulls recordings from the PLAUD cloud via the API client."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from plaud_brain.config import Config
from plaud_brain.models import RawRecording
from plaud_brain.plaud import PlaudCloudClient


class CloudSource:
    name = "cloud"

    def __init__(self, config: Config, client: PlaudCloudClient | None = None) -> None:
        self._cfg = config
        self._client = client or PlaudCloudClient(
            config.plaud.token, region=config.plaud.region
        )

    def iter_recordings(self) -> Iterable[RawRecording]:
        for rec in self._client.list_recordings(limit=self._cfg.plaud.list_limit):
            yield RawRecording(
                uid=f"cloud:{rec.id}",
                title=rec.title,
                source=self.name,
                created_at=rec.created_at,
                duration_ms=rec.duration_ms,
                remote_url=None,  # fetched lazily via ensure_local_audio
                extra={"plaud_id": rec.id},
            )

    def ensure_local_audio(self, rec: RawRecording, cache_dir: Path) -> Path:
        if rec.audio_path and rec.audio_path.exists():
            return rec.audio_path
        cache_dir.mkdir(parents=True, exist_ok=True)
        plaud_id = rec.extra["plaud_id"]
        dest = cache_dir / f"{plaud_id}.mp3"
        if not dest.exists() or dest.stat().st_size == 0:
            self._client.download_audio(plaud_id, dest)
        rec.audio_path = dest
        return dest
