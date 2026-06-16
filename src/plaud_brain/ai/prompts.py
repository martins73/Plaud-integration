"""Prompt templates for the Gemini transcription and summarization steps."""

TRANSCRIBE_INSTRUCTION = """\
You are a precise audio transcriptionist. Transcribe the attached audio \
recording verbatim into clean, readable text.

Rules:
- Output ONLY the transcript text. No preamble, no explanations, no code fences.
- When multiple speakers are present, label turns as "Speaker 1:", "Speaker 2:", etc.
  Keep the same label for the same voice throughout.
- Use natural paragraph breaks. Add light punctuation for readability.
- Do not summarize, translate, or omit content.
- If a passage is inaudible, write [inaudible].
{language_line}"""

SUMMARIZE_INSTRUCTION = """\
You are an assistant that turns a meeting/voice-note transcript into a concise \
note for a personal knowledge base (a "second brain").

Produce Markdown with exactly these sections, in this order:

## TL;DR
A 1-3 sentence summary.

## Key Points
- Bullet points of the most important information.

## Action Items
- [ ] Concrete tasks, decisions, or follow-ups. Write "None identified." if there are none.

## Topics
A short comma-separated list of 3-7 topical keywords (no leading hashes).

Be faithful to the transcript. Do not invent facts. Keep it tight.

Recording title: {title}

Transcript:
---
{transcript}
---"""


def transcribe_instruction(language: str) -> str:
    if language and language.lower() != "auto":
        language_line = f"- The spoken language is '{language}'. Transcribe in that language."
    else:
        language_line = "- Detect the spoken language and transcribe in that same language."
    return TRANSCRIBE_INSTRUCTION.format(language_line=language_line)


def summarize_instruction(title: str, transcript: str) -> str:
    return SUMMARIZE_INSTRUCTION.format(title=title, transcript=transcript)
