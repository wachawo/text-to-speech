#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for libs.config — user-config bootstrap, persistence, and dotenv priority chain.

Each test patches USER_CONFIG_PATH/USER_CONFIG_DIR in the module so the real
~/.config/ttsgen.conf on the developer's machine is never touched.
"""

import os
from pathlib import Path

import pytest

# Local imports
from libs import config as cfg


@pytest.fixture
def isolated_user_config(tmp_path, monkeypatch):
    """Redirect USER_CONFIG_DIR/USER_CONFIG_PATH at the module so file-IO is sandboxed."""
    user_dir = tmp_path / "fakehome" / ".config"
    user_path = user_dir / "ttsgen.conf"
    monkeypatch.setattr(cfg, "USER_CONFIG_DIR", user_dir)
    monkeypatch.setattr(cfg, "USER_CONFIG_PATH", user_path)
    return user_path


# ensure_user_config


def test_ensure_user_config_creates_with_defaults(isolated_user_config):
    """A missing user config is created from the template and its path returned."""
    assert not isolated_user_config.exists()
    returned = cfg.ensure_user_config()
    assert returned == isolated_user_config
    body = isolated_user_config.read_text()
    # Must contain the load-order comment + at least one example key
    assert "Load order" in body
    assert "TTS_ENGINE=" in body


def test_ensure_user_config_idempotent_on_existing_file(isolated_user_config):
    """An existing user config is left byte-for-byte untouched."""
    isolated_user_config.parent.mkdir(parents=True)
    isolated_user_config.write_text("USER_TWEAK=1\n")
    cfg.ensure_user_config()
    # Must NOT clobber existing content.
    assert isolated_user_config.read_text() == "USER_TWEAK=1\n"


def test_ensure_user_config_silent_on_oserror(monkeypatch, tmp_path, caplog):
    """If the directory cannot be created, ensure_user_config must NOT raise.
    Config files are an optional convenience — failure is non-fatal."""
    blocked = tmp_path / "blocked" / ".config"
    monkeypatch.setattr(cfg, "USER_CONFIG_DIR", blocked)
    monkeypatch.setattr(cfg, "USER_CONFIG_PATH", blocked / "ttsgen.conf")

    def fail_mkdir(*a, **kw):
        """Simulate a read-only filesystem when the config directory is created."""
        raise PermissionError("readonly fs")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    with caplog.at_level("WARNING"):
        path = cfg.ensure_user_config()
    assert path == blocked / "ttsgen.conf"  # path returned even on failure
    assert any("Could not create" in r.message for r in caplog.records)


# persist_config_value


def test_persist_appends_when_key_absent(isolated_user_config):
    """A key not yet present is appended to the user config."""
    cfg.persist_config_value("MY_NEW_KEY", "value1")
    body = isolated_user_config.read_text()
    assert "MY_NEW_KEY=value1" in body


def test_persist_replaces_uncommented_existing_key(isolated_user_config):
    """An existing live KEY=... line must be replaced, not duplicated."""
    isolated_user_config.parent.mkdir(parents=True)
    isolated_user_config.write_text("FOO=bar\nBAZ=qux\n")
    cfg.persist_config_value("FOO", "newbar")
    body = isolated_user_config.read_text()
    assert body.count("FOO=") == 1
    assert "FOO=newbar" in body
    assert "BAZ=qux" in body  # other keys untouched


def test_persist_uncomments_commented_key(isolated_user_config):
    """`# KEY=value` (the template style) must turn into `KEY=newvalue`."""
    isolated_user_config.parent.mkdir(parents=True)
    isolated_user_config.write_text("# COQUITTS_MODEL=old\n# OTHER=keep\n")
    cfg.persist_config_value("COQUITTS_MODEL", "newmodel")
    body = isolated_user_config.read_text()
    assert "COQUITTS_MODEL=newmodel" in body
    assert "# OTHER=keep" in body  # untouched commented keys preserved


def test_persist_only_replaces_first_match(isolated_user_config):
    """If the file has duplicate KEY entries, only the first is replaced —
    callers should not rely on dedup, but the contract pins down stability."""
    isolated_user_config.parent.mkdir(parents=True)
    isolated_user_config.write_text("FOO=a\nFOO=b\n")
    cfg.persist_config_value("FOO", "c")
    body = isolated_user_config.read_text()
    assert "FOO=c" in body
    assert "FOO=b" in body  # second occurrence left alone


# load_config — dotenv priority chain


def test_load_config_no_op_when_dotenv_missing(monkeypatch, isolated_user_config, tmp_path):
    """Without python-dotenv installed, load_config must early-return cleanly."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cfg, "DOTENV_AVAILABLE", False)
    cfg.load_config()  # must not raise


def test_load_config_priority_local_over_shared_env(monkeypatch, isolated_user_config, tmp_path):
    """`.env.local` must win over `.env` (the bug the user originally hit)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("MY_KEY=shared_loses\n")
    (tmp_path / ".env.local").write_text("MY_KEY=local_wins\n")
    monkeypatch.delenv("MY_KEY", raising=False)
    cfg.load_config()
    assert os.environ.get("MY_KEY") == "local_wins"


def test_load_config_dotenv_beats_user_config(monkeypatch, isolated_user_config, tmp_path):
    """.env is priority 3, ~/.config/ttsgen.conf is priority 4 — .env wins."""
    monkeypatch.chdir(tmp_path)
    isolated_user_config.parent.mkdir(parents=True, exist_ok=True)
    isolated_user_config.write_text("USER_PRIORITY=user_loses\n")
    (tmp_path / ".env").write_text("USER_PRIORITY=env_wins\n")
    monkeypatch.delenv("USER_PRIORITY", raising=False)
    cfg.load_config()
    assert os.environ.get("USER_PRIORITY") == "env_wins"


def test_load_config_process_env_beats_files(monkeypatch, isolated_user_config, tmp_path):
    """Real process env outranks every file except .env.local, which is absent here."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PROCESS_ENV_KEY=from_env_file\n")
    monkeypatch.setenv("PROCESS_ENV_KEY", "from_process")
    cfg.load_config()
    assert os.environ["PROCESS_ENV_KEY"] == "from_process"
