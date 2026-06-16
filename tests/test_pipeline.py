"""End-to-end pipeline test using fakes (no network, no Gemini, no PLAUD)."""

from datetime import UTC, datetime
from pathlib import Path

from plaud_brain.config import Config, ObsidianConfig, PipelineConfig
from plaud_brain.models import ProcessedContent, RawRecording
from plaud_brain.pipeline import Pipeline
from plaud_brain.state import ProcessedStore


class FakeSource:
    name = "fake"

    def __init__(self, recs):
        self._recs = recs

    def iter_recordings(self):
        yield from self._recs

    def ensure_local_audio(self, rec, cache_dir):
        return rec.audio_path


class FakeProcessor:
    def __init__(self):
        self.calls = 0

    def process(self, audio_path, *, title):
        self.calls += 1
        return ProcessedContent(
            transcript=f"transcript of {title}",
            summary="## TL;DR\nfake",
            model="fake-model",
        )


def _config(tmp_path):
    return Config(
        obsidian=ObsidianConfig(
            vault_path=str(tmp_path / "vault"), notes_subdir="Plaud", copy_audio=False
        ),
        pipeline=PipelineConfig(
            audio_cache_dir=str(tmp_path / "cache"),
            state_file=str(tmp_path / "state.json"),
        ),
    )


def _rec(uid, title, audio):
    return RawRecording(
        uid=uid,
        title=title,
        source="fake",
        created_at=datetime(2026, 6, 16, tzinfo=UTC),
        audio_path=audio,
    )


def test_pipeline_processes_and_dedupes(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    cfg = _config(tmp_path)
    proc = FakeProcessor()
    store = ProcessedStore(cfg.pipeline.state_path)
    source = FakeSource([_rec("fake:1", "First Note", audio)])

    pipe = Pipeline(cfg, processor=proc, store=store)
    r1 = pipe.run([source])
    assert r1.processed == 1 and r1.skipped == 0
    assert proc.calls == 1
    assert len(r1.notes) == 1
    assert Path(r1.notes[0]).exists()

    # Second run: already processed -> skipped, no new Gemini call.
    r2 = pipe.run([source])
    assert r2.processed == 0 and r2.skipped == 1
    assert proc.calls == 1


def test_pipeline_dry_run_writes_nothing(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    cfg = _config(tmp_path)
    proc = FakeProcessor()
    store = ProcessedStore(cfg.pipeline.state_path)
    pipe = Pipeline(cfg, processor=proc, store=store)

    result = pipe.run([FakeSource([_rec("fake:1", "N", audio)])], dry_run=True)
    assert result.processed == 1
    assert proc.calls == 0
    assert store.has("fake:1") is False
    assert not (tmp_path / "vault").exists()


def test_pipeline_reprocess(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    cfg = _config(tmp_path)
    proc = FakeProcessor()
    store = ProcessedStore(cfg.pipeline.state_path)
    store.mark("fake:1", source="fake", note_path="old", title="N")
    pipe = Pipeline(cfg, processor=proc, store=store)

    result = pipe.run([FakeSource([_rec("fake:1", "N", audio)])], reprocess=True)
    assert result.processed == 1
    assert proc.calls == 1


def test_pipeline_limit(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    cfg = _config(tmp_path)
    recs = [_rec(f"fake:{i}", f"N{i}", audio) for i in range(5)]
    pipe = Pipeline(cfg, processor=FakeProcessor(), store=ProcessedStore(cfg.pipeline.state_path))
    result = pipe.run([FakeSource(recs)], limit=2)
    assert result.processed == 2


def test_pipeline_continues_on_failure(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    cfg = _config(tmp_path)

    class Boom(FakeProcessor):
        def process(self, audio_path, *, title):
            if title == "bad":
                raise RuntimeError("gemini exploded")
            return super().process(audio_path, title=title)

    recs = [_rec("fake:1", "bad", audio), _rec("fake:2", "good", audio)]
    pipe = Pipeline(cfg, processor=Boom(), store=ProcessedStore(cfg.pipeline.state_path))
    result = pipe.run([FakeSource(recs)])
    assert result.failed == 1
    assert result.processed == 1
