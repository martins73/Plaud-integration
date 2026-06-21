"""Writes processed recordings as Markdown notes into an Obsidian vault."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from plaud_brain.config import ObsidianConfig
from plaud_brain.models import ProcessedContent, RawRecording

_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


def slugify(text: str, *, max_len: int = 60) -> str:
    slug = _SLUG_RE.sub("-", text).strip("-").lower()
    return slug[:max_len].strip("-") or "untitled"


def _yaml_escape(value: str) -> str:
    """Quote a scalar for YAML frontmatter if needed."""
    if value == "" or re.search(r"[:#\[\]{}\",&*!|>'%@`]", value) or value != value.strip():
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


class ObsidianVault:
    def __init__(self, config: ObsidianConfig) -> None:
        self._cfg = config

    def note_path(self, rec: RawRecording) -> Path:
        date = rec.created_at.strftime("%Y-%m-%d")
        filename = f"{date}-{slugify(rec.title)}.md"
        return self._cfg.notes_dir / filename

    def write_note(
        self,
        rec: RawRecording,
        content: ProcessedContent,
        audio_path: Path | None,
    ) -> Path:
        notes_dir = self._cfg.notes_dir
        notes_dir.mkdir(parents=True, exist_ok=True)

        audio_link = None
        if self._cfg.copy_audio and audio_path and audio_path.exists():
            audio_link = self._copy_audio(rec, audio_path)

        note = self.note_path(rec)
        note.write_text(self._render(rec, content, audio_link), encoding="utf-8")
        return note

    # ------------------------------------------------------------------

    def _copy_audio(self, rec: RawRecording, audio_path: Path) -> str:
        attachments = self._cfg.attachments_dir
        attachments.mkdir(parents=True, exist_ok=True)
        date = rec.created_at.strftime("%Y-%m-%d")
        dest = attachments / f"{date}-{slugify(rec.title)}{audio_path.suffix.lower()}"
        if dest.resolve() != audio_path.resolve():
            shutil.copy2(audio_path, dest)
        # Obsidian embeds resolve by vault-relative path or filename.
        return f"{self._cfg.attachments_subdir}/{dest.name}"

    def _render(
        self,
        rec: RawRecording,
        content: ProcessedContent,
        audio_link: str | None,
    ) -> str:
        tags = list(self._cfg.default_tags)
        fm = [
            "---",
            f"title: {_yaml_escape(rec.title)}",
            f"date: {rec.created_at.strftime('%Y-%m-%d')}",
            f"created: {rec.created_at.isoformat()}",
            f"source: {rec.source}",
        ]
        if rec.extra.get("plaud_id"):
            fm.append(f"plaud_id: {_yaml_escape(str(rec.extra['plaud_id']))}")
        if rec.duration_ms:
            fm.append(f"duration: {rec.duration_display}")
        if content.model:
            fm.append(f"transcribed_with: {_yaml_escape(content.model)}")
        if self._cfg.note_status:
            fm.append(f"status: {_yaml_escape(self._cfg.note_status)}")
        fm.append("tags:")
        fm.extend(f"  - {t}" for t in tags)
        fm.append("---")

        body = [f"# {rec.title}", ""]
        if audio_link:
            body += [f"![[{audio_link}]]", ""]

        summary = content.summary.strip()
        if summary:
            body += [summary, ""]

        body += [
            "## Transcript",
            "",
            content.transcript.strip() or "_No transcript produced._",
            "",
        ]
        return "\n".join(fm) + "\n\n" + "\n".join(body).rstrip() + "\n"
