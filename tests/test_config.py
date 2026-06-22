import textwrap

import pytest

from plaud_brain.config import ConfigError, _strip_bearer, load_config


def test_strip_bearer():
    assert _strip_bearer("bearer eyJabc") == "eyJabc"
    assert _strip_bearer("Bearer eyJabc") == "eyJabc"
    assert _strip_bearer("  'eyJabc'  ") == "eyJabc"
    assert _strip_bearer("eyJabc") == "eyJabc"


def test_load_defaults_without_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PLAUD_TOKEN", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = load_config()
    assert cfg.gemini.model == "gemini-3.5-flash"
    assert cfg.plaud.region == "default"
    assert cfg.usb.enabled is False
    assert cfg.obsidian.default_tags == ["plaud", "voice-note"]


def test_load_from_toml_and_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text(
        textwrap.dedent(
            """
            [plaud]
            region = "apse1"
            list_limit = 5

            [usb]
            mount_path = "/Volumes/PLAUD_NOTE"

            [gemini]
            model = "gemini-2.5-pro"

            [obsidian]
            vault_path = "~/Vault"
            notes_subdir = "Voice"

            [pipeline]
            """
        ).strip()
    )
    monkeypatch.setenv("PLAUD_TOKEN", "bearer tok123")
    monkeypatch.setenv("GEMINI_API_KEY", "key456")
    cfg = load_config("config.toml")
    assert cfg.plaud.region == "apse1"
    assert cfg.plaud.list_limit == 5
    assert cfg.plaud.token == "tok123"  # bearer stripped
    assert cfg.usb.enabled is True
    assert cfg.gemini.model == "gemini-2.5-pro"
    assert cfg.gemini.api_key == "key456"
    assert cfg.obsidian.notes_dir.name == "Voice"


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml")
