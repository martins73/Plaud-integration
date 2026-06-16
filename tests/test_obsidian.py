from datetime import UTC, datetime

from plaud_brain.config import ObsidianConfig
from plaud_brain.models import ProcessedContent, RawRecording
from plaud_brain.sinks.obsidian import ObsidianVault, slugify


def _rec(**kw):
    base = dict(
        uid="cloud:abc",
        title="Team Sync: Q3 Planning",
        source="cloud",
        created_at=datetime(2026, 6, 16, 9, 30, tzinfo=UTC),
        duration_ms=125000,
        extra={"plaud_id": "abc"},
    )
    base.update(kw)
    return RawRecording(**base)


def test_slugify():
    assert slugify("Team Sync: Q3 Planning") == "team-sync-q3-planning"
    assert slugify("   ") == "untitled"
    assert slugify("a/b\\c") == "a-b-c"


def test_write_note_creates_markdown(tmp_path):
    cfg = ObsidianConfig(vault_path=str(tmp_path), notes_subdir="Plaud", copy_audio=False)
    vault = ObsidianVault(cfg)
    content = ProcessedContent(
        transcript="Speaker 1: Hello.\nSpeaker 2: Hi.",
        summary="## TL;DR\nA short sync.",
        model="gemini-2.5-flash",
    )
    note = vault.write_note(_rec(), content, audio_path=None)

    assert note.exists()
    assert note.name == "2026-06-16-team-sync-q3-planning.md"
    text = note.read_text()
    assert text.startswith("---\n")
    assert 'title: "Team Sync: Q3 Planning"' in text  # colon forces quoting
    assert "source: cloud" in text
    assert "plaud_id: abc" in text
    assert "duration: 2:05" in text
    assert "transcribed_with: gemini-2.5-flash" in text
    assert "  - plaud" in text
    assert "## TL;DR" in text
    assert "## Transcript" in text
    assert "Speaker 1: Hello." in text


def test_write_note_copies_audio(tmp_path):
    audio = tmp_path / "src.mp3"
    audio.write_bytes(b"ID3fakeaudio")
    cfg = ObsidianConfig(
        vault_path=str(tmp_path / "vault"),
        notes_subdir="Plaud",
        copy_audio=True,
        attachments_subdir="Plaud/audio",
    )
    vault = ObsidianVault(cfg)
    content = ProcessedContent(transcript="hi", summary="## TL;DR\nx")
    note = vault.write_note(_rec(), content, audio_path=audio)

    copied = tmp_path / "vault" / "Plaud" / "audio" / "2026-06-16-team-sync-q3-planning.mp3"
    assert copied.exists()
    assert copied.read_bytes() == b"ID3fakeaudio"
    assert "![[Plaud/audio/2026-06-16-team-sync-q3-planning.mp3]]" in note.read_text()
