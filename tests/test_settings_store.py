from __future__ import annotations

import json
from pathlib import Path

from gigaam_capture.config import SettingsStore, build_app_paths
from gigaam_capture.models import AppSettings


def test_build_app_paths_exposes_log_file(tmp_path: Path):
    paths = build_app_paths(tmp_path)

    assert paths.log_path == tmp_path / "logs" / "app.log"


def test_load_returns_defaults_when_file_is_missing(app_paths):
    store = SettingsStore(app_paths)

    assert store.load() == AppSettings()


def test_load_falls_back_to_defaults_on_corrupt_json(app_paths):
    app_paths.settings_path.write_text("{not json", encoding="utf-8")

    assert SettingsStore(app_paths).load() == AppSettings()


def test_load_falls_back_to_defaults_on_non_object_payload(app_paths):
    app_paths.settings_path.write_text("[1, 2, 3]", encoding="utf-8")

    assert SettingsStore(app_paths).load() == AppSettings()


def test_load_ignores_unknown_keys_and_keeps_known_values(app_paths):
    app_paths.settings_path.write_text(
        json.dumps(
            {
                "hotkey": "<ctrl>+<alt>+j",
                "model_name": "v3_ctc",
                "future_option": True,
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsStore(app_paths).load()

    assert settings.hotkey == "<ctrl>+<alt>+j"
    assert settings.model_name == "v3_ctc"
    assert settings.target_mode == AppSettings().target_mode


def test_load_replaces_invalid_values_with_defaults(app_paths):
    defaults = AppSettings()
    app_paths.settings_path.write_text(
        json.dumps(
            {
                "hotkey": "   ",
                "max_duration_seconds": 0,
                "sample_rate": "16000",
                "channels": True,
                "fallback_to_clipboard": "yes",
                "model_name": None,
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsStore(app_paths).load()

    assert settings.hotkey == defaults.hotkey
    assert settings.max_duration_seconds == defaults.max_duration_seconds
    assert settings.sample_rate == defaults.sample_rate
    assert settings.channels == defaults.channels
    assert settings.fallback_to_clipboard is defaults.fallback_to_clipboard
    assert settings.model_name == defaults.model_name


def test_save_and_load_roundtrip(app_paths):
    store = SettingsStore(app_paths)
    expected = AppSettings(
        hotkey="<ctrl>+<alt>+j",
        model_name="v3_ctc",
        max_duration_seconds=12,
        sample_rate=22050,
        channels=2,
        target_mode="clipboard",
        fallback_to_clipboard=False,
    )

    store.save(expected)

    assert store.load() == expected
