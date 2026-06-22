"""Configuration loading from config.toml + environment (.env for secrets)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_CONFIG_NAME = "config.toml"


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(p)))


@dataclass(slots=True)
class PlaudConfig:
    region: str = "default"
    list_limit: int = 50
    token: str = ""  # from PLAUD_TOKEN env / .env


@dataclass(slots=True)
class UsbConfig:
    mount_path: str = ""
    folders: list[str] = field(default_factory=lambda: ["NOTES", "CALLS"])

    @property
    def enabled(self) -> bool:
        return bool(self.mount_path.strip())


@dataclass(slots=True)
class GeminiConfig:
    model: str = "gemini-3.5-flash"
    language: str = "auto"
    api_key: str = ""  # from GEMINI_API_KEY env / .env


@dataclass(slots=True)
class ObsidianConfig:
    vault_path: str = "~/Obsidian/SecondBrain"
    notes_subdir: str = "Plaud"
    copy_audio: bool = True
    attachments_subdir: str = "Plaud/audio"
    default_tags: list[str] = field(default_factory=lambda: ["plaud", "voice-note"])
    # Value of the `status:` frontmatter field on new notes, so a downstream
    # agent can find notes it hasn't ingested yet. Set to "" to omit the field.
    note_status: str = "unprocessed"

    @property
    def notes_dir(self) -> Path:
        return _expand(self.vault_path) / self.notes_subdir

    @property
    def attachments_dir(self) -> Path:
        return _expand(self.vault_path) / self.attachments_subdir


@dataclass(slots=True)
class PipelineConfig:
    audio_cache_dir: str = "~/.cache/plaud-brain/audio"
    state_file: str = "~/.local/state/plaud-brain/processed.json"

    @property
    def audio_cache(self) -> Path:
        return _expand(self.audio_cache_dir)

    @property
    def state_path(self) -> Path:
        return _expand(self.state_file)


@dataclass(slots=True)
class Config:
    plaud: PlaudConfig = field(default_factory=PlaudConfig)
    usb: UsbConfig = field(default_factory=UsbConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    obsidian: ObsidianConfig = field(default_factory=ObsidianConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)


def _section(data: dict, name: str) -> dict:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"[{name}] must be a table in the config file")
    return section


class ConfigError(Exception):
    """Raised when configuration is invalid."""


def load_config(path: str | Path | None = None) -> Config:
    """Load config from a TOML file (if present) and overlay secrets from env.

    Secrets are never read from the TOML file; they come from environment
    variables (loaded from a local ``.env`` if present):
        PLAUD_TOKEN, GEMINI_API_KEY
    """
    load_dotenv()  # populate os.environ from .env if present

    data: dict = {}
    if path is None:
        candidate = Path(DEFAULT_CONFIG_NAME)
        if candidate.exists():
            path = candidate
    if path is not None:
        path = Path(path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        with open(path, "rb") as f:
            data = tomllib.load(f)

    cfg = Config(
        plaud=PlaudConfig(**_section(data, "plaud")),
        usb=UsbConfig(**_section(data, "usb")),
        gemini=GeminiConfig(**_section(data, "gemini")),
        obsidian=ObsidianConfig(**_section(data, "obsidian")),
        pipeline=PipelineConfig(**_section(data, "pipeline")),
    )

    # Secrets from environment override anything else.
    token = os.environ.get("PLAUD_TOKEN", "").strip()
    if token:
        cfg.plaud.token = _strip_bearer(token)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        cfg.gemini.api_key = api_key

    return cfg


def _strip_bearer(token: str) -> str:
    """Accept tokens pasted with or without the leading 'bearer ' prefix."""
    token = token.strip().strip("\"'")
    lowered = token.lower()
    if lowered.startswith("bearer "):
        return token[len("bearer ") :].strip()
    return token
