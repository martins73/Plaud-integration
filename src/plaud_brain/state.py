"""Tracks which recordings have already been processed (idempotent syncs)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class ProcessedStore:
    """A tiny JSON-backed record of processed recordings, keyed by uid.

    Each entry stores when it was processed, which source it came from, and
    the note path that was written. This lets ``sync`` skip work it has
    already done and lets ``status`` report what has been handled.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        if not isinstance(self._data, dict):
            self._data = {}

    def has(self, uid: str) -> bool:
        return uid in self._data

    def get(self, uid: str) -> dict | None:
        return self._data.get(uid)

    def mark(self, uid: str, *, source: str, note_path: str, title: str) -> None:
        self._data[uid] = {
            "source": source,
            "note_path": note_path,
            "title": title,
            "processed_at": datetime.now(tz=UTC).isoformat(),
        }
        self._save()

    def forget(self, uid: str) -> bool:
        if uid in self._data:
            del self._data[uid]
            self._save()
            return True
        return False

    @property
    def entries(self) -> dict[str, dict]:
        return dict(self._data)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
