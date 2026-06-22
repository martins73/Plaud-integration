"""Gemini-backed transcription and summarization.

Uses the google-genai SDK. The audio file is uploaded via the Files API and
passed to the model for transcription; the resulting transcript is then
summarized. The SDK is imported lazily so the rest of the package (and the
test suite) does not require the dependency or an API key to be present.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from plaud_brain.ai.prompts import summarize_instruction, transcribe_instruction
from plaud_brain.models import ProcessedContent

_MIME_BY_EXT = {
    ".mp3": "audio/mp3",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".asr": "audio/ogg",
}


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _MIME_BY_EXT:
        return _MIME_BY_EXT[ext]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


class GeminiProcessor:
    """Transcribe + summarize audio with a single Gemini model."""

    def __init__(self, api_key: str, *, model: str = "gemini-3.5-flash", language: str = "auto"):
        if not api_key:
            raise ValueError(
                "No GEMINI_API_KEY. Add it to your .env (get a key at "
                "https://aistudio.google.com/apikey)."
            )
        self.model = model
        self.language = language
        self._api_key = api_key
        self._client = None  # lazily created

    def _get_client(self):
        if self._client is None:
            from google import genai  # imported lazily

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def transcribe(self, audio_path: Path) -> str:
        client = self._get_client()
        uploaded = client.files.upload(
            file=str(audio_path),
            config={"mime_type": _guess_mime(audio_path)},
        )
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=[transcribe_instruction(self.language), uploaded],
            )
        finally:
            # Best-effort cleanup of the remote uploaded file.
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass
        return (response.text or "").strip()

    def summarize(self, transcript: str, *, title: str) -> str:
        client = self._get_client()
        response = client.models.generate_content(
            model=self.model,
            contents=summarize_instruction(title, transcript),
        )
        return (response.text or "").strip()

    def process(self, audio_path: Path, *, title: str) -> ProcessedContent:
        transcript = self.transcribe(audio_path)
        summary = self.summarize(transcript, title=title) if transcript else ""
        return ProcessedContent(
            transcript=transcript,
            summary=summary,
            language=self.language,
            model=self.model,
        )
