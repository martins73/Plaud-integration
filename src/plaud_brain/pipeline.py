"""Orchestrates the sync: source -> Gemini -> Obsidian, with de-duplication."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from plaud_brain.ai import GeminiProcessor
from plaud_brain.config import Config
from plaud_brain.models import RawRecording
from plaud_brain.sinks import ObsidianVault
from plaud_brain.sources.base import AudioSource
from plaud_brain.state import ProcessedStore

Logger = Callable[[str], None]


@dataclass(slots=True)
class SyncResult:
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    notes: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []


class Pipeline:
    def __init__(
        self,
        config: Config,
        *,
        processor: GeminiProcessor | None = None,
        vault: ObsidianVault | None = None,
        store: ProcessedStore | None = None,
        log: Logger | None = None,
    ) -> None:
        self.cfg = config
        self.vault = vault or ObsidianVault(config.obsidian)
        self.store = store or ProcessedStore(config.pipeline.state_path)
        self._processor = processor
        self._log: Logger = log or (lambda _msg: None)

    @property
    def processor(self) -> GeminiProcessor:
        if self._processor is None:
            self._processor = GeminiProcessor(
                self.cfg.gemini.api_key,
                model=self.cfg.gemini.model,
                language=self.cfg.gemini.language,
            )
        return self._processor

    def run(
        self,
        sources: Iterable[AudioSource],
        *,
        limit: int | None = None,
        reprocess: bool = False,
        dry_run: bool = False,
    ) -> SyncResult:
        result = SyncResult()
        for source in sources:
            self._log(f"Scanning source: {source.name}")
            count = 0
            for rec in source.iter_recordings():
                if limit is not None and count >= limit:
                    break
                count += 1
                if not reprocess and self.store.has(rec.uid):
                    result.skipped += 1
                    self._log(f"  skip (already processed): {rec.title}")
                    continue
                try:
                    note = self._process_one(source, rec, dry_run=dry_run)
                    result.processed += 1
                    if note:
                        result.notes.append(note)
                except Exception as exc:  # noqa: BLE001 - report and continue
                    result.failed += 1
                    self._log(f"  FAILED: {rec.title}: {exc}")
        return result

    def _process_one(self, source: AudioSource, rec: RawRecording, *, dry_run: bool) -> str | None:
        if dry_run:
            self._log(f"  would process: {rec.title}  [{rec.source}]")
            return None

        self._log(f"  fetching audio: {rec.title}")
        audio_path = source.ensure_local_audio(rec, self.cfg.pipeline.audio_cache)

        self._log(f"  transcribing + summarizing with {self.cfg.gemini.model} ...")
        content = self.processor.process(audio_path, title=rec.title)

        note = self.vault.write_note(rec, content, audio_path)
        self.store.mark(
            rec.uid, source=rec.source, note_path=str(note), title=rec.title
        )
        self._log(f"  wrote note: {note}")
        return str(note)
