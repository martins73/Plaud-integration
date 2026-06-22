# plaud-brain

Pull voice recordings off your **PLAUD Note** (Pro), transcribe and summarize
them with **Google Gemini**, and file the results as Markdown notes into your
**Obsidian** second brain.

You bring your own Gemini API key — your audio is processed by *your* account,
not by PLAUD's built-in AI and not by any third-party server. Everything else
runs locally.

```
PLAUD Note ──► [ cloud API | USB folder ] ──► Gemini (transcribe + summarize) ──► Obsidian vault
```

> **Heads-up on the PLAUD cloud source.** PLAUD has no official public API.
> The cloud source uses endpoints reverse-engineered from the PLAUD web app
> (the same approach community tools use). It works today but can break if
> PLAUD changes their API. The **USB source** does not depend on any of that
> and is the reliable fallback.

---

## Features

- **Two ingest paths**
  - **Cloud** — logs into your PLAUD account with a session token and downloads
    recordings automatically.
  - **USB** — reads raw audio straight off the device's `NOTES/` and `CALLS/`
    folders when you plug it in (enable *Access via USB* in the PLAUD app).
- **Your own AI** — transcription + structured summary via Gemini, with speaker
  labels and an *Action Items* checklist.
- **Obsidian-native output** — one Markdown note per recording, with YAML
  frontmatter, an embedded audio player, the summary, and the full transcript.
- **Idempotent** — a local state file tracks what's been processed, so re-running
  `sync` only handles new recordings.
- **Configurable** — everything via `config.toml`; secrets via `.env`.

## Requirements

- Python 3.11+
- A PLAUD account (for the cloud source) and/or the device + USB cable
- A Google Gemini API key — https://aistudio.google.com/apikey

## Install

```bash
git clone <this-repo> Plaud-integration
cd Plaud-integration
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Configure

```bash
cp .env.example .env            # secrets (gitignored)
cp config.example.toml config.toml
```

1. **Gemini key** — put `GEMINI_API_KEY=...` in `.env`.
2. **PLAUD token** (for the cloud source):
   - Sign in at https://web.plaud.ai
   - DevTools → Application → Local Storage → `https://web.plaud.ai` → copy the
     value of **`tokenstr`** (a long `bearer eyJ...` string, valid ~10 months).
   - Save it: `plaud-brain auth` (paste when prompted) — or set `PLAUD_TOKEN` in `.env`.
3. **Obsidian vault** — set `[obsidian].vault_path` in `config.toml`.
4. **USB** (optional) — set `[usb].mount_path` to where the device mounts
   (e.g. `/Volumes/PLAUD_NOTE` on macOS).

See `config.example.toml` for every option (region, model, tags, paths, …).

## Usage

```bash
# Sanity-check the cloud connection
plaud-brain list

# See what would be processed, without calling Gemini or writing notes
plaud-brain sync --dry-run

# Process new recordings from all configured sources into your vault
plaud-brain sync

# Only one source, cap the number processed
plaud-brain sync --source cloud --limit 5
plaud-brain sync --source usb

# Re-process something you've already done
plaud-brain sync --reprocess

# Ignore recordings forever (e.g. the PLAUD demo clips or empty recordings).
# Use the ids shown by `plaud-brain list`; sync will skip them from now on.
plaud-brain skip 168b0d8a4866...  f7503a83a56d...
plaud-brain unskip 168b0d8a4866...      # changed your mind

# What's been processed so far
plaud-brain status -v
```

Run it on a schedule (cron, launchd, Task Scheduler) to keep your vault in sync.

### What a note looks like

```markdown
---
title: "Team Sync: Q3 Planning"
date: 2026-06-16
source: cloud
plaud_id: 66a1...
duration: 2:05
transcribed_with: gemini-3.5-flash
tags:
  - plaud
  - voice-note
---

# Team Sync: Q3 Planning

![[Plaud/audio/2026-06-16-team-sync-q3-planning.mp3]]

## TL;DR
Short summary of the conversation.

## Key Points
- ...

## Action Items
- [ ] ...

## Topics
planning, q3, roadmap

## Transcript

Speaker 1: ...
Speaker 2: ...
```

## How it fits together

```
src/plaud_brain/
├── cli.py            # argparse CLI: auth / list / sync / status
├── config.py         # config.toml + .env loading
├── pipeline.py       # orchestration + de-duplication
├── state.py          # processed.json tracking
├── models.py         # RawRecording, ProcessedContent
├── plaud/            # self-contained PLAUD cloud client (reverse-engineered)
├── sources/          # cloud + usb ingest (AudioSource protocol)
├── ai/               # Gemini transcription + summarization (+ prompts)
└── sinks/            # Obsidian Markdown writer
```

Each layer is swappable: add a `NotionSink`, a different transcription provider,
or another source by implementing the same small interface.

## Development

```bash
pip install -e ".[dev]"
pytest          # full suite runs offline (no network / API keys needed)
ruff check .
mypy src
```

The tests stub out PLAUD and Gemini, so they run without credentials.

## Roadmap / second-brain integration

- [ ] Push the *Action Items* into a tasks system / daily note
- [ ] Optional Notion or Logseq sink
- [ ] Auto-linking entities (people, projects) for graph connections
- [ ] Incremental cloud sync via stored cursor instead of full list scans

## Legal / privacy

This is an unofficial, personal-use tool and is not affiliated with PLAUD.
The cloud source relies on a reverse-engineered API; use it with your own
account and at your own risk, and review PLAUD's Terms of Service. Audio is sent
to Google's Gemini API for processing under your own API key — see Google's data
-usage terms for the API.

## Credits

The reverse-engineered PLAUD endpoints are well-documented by the community,
notably `arbuzmell/plaud-api`, `leonardsellem/plaud-sync-for-obsidian`, and
`openplaud/openplaud` (Riffado). This project reimplements only the minimal read
paths it needs.
