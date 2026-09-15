from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

from platformdirs import user_data_dir

from .log import get_logger
from .models import AppPaths, AppSettings

APP_NAME = "GigaAM Capture"
APP_AUTHOR = "GigaAM"

logger = get_logger("config")

_MISSING = object()


def build_app_paths(base_dir: Path | None = None) -> AppPaths:
    root = base_dir or Path(user_data_dir(APP_NAME, APP_AUTHOR))
    history_dir = root / "history"
    recordings_dir = history_dir / "recordings"
    settings_path = root / "settings.json"
    history_log = history_dir / "history.jsonl"
    log_path = root / "logs" / "app.log"
    return AppPaths(
        root=root,
        history_dir=history_dir,
        recordings_dir=recordings_dir,
        history_log=history_log,
        settings_path=settings_path,
        log_path=log_path,
    )


def ensure_app_dirs(paths: AppPaths) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.history_dir.mkdir(parents=True, exist_ok=True)
    paths.recordings_dir.mkdir(parents=True, exist_ok=True)
    paths.log_path.parent.mkdir(parents=True, exist_ok=True)


def settings_from_payload(payload: object) -> AppSettings:
    """Build settings from a raw decoded JSON payload.

    Unknown keys are ignored and invalid values fall back to defaults so a
    hand-edited or partially corrupted ``settings.json`` never prevents the app
    from starting.
    """
    defaults = AppSettings()
    if not isinstance(payload, dict):
        logger.warning("Settings payload is not a JSON object; defaults applied")
        return defaults

    known = {field.name for field in fields(AppSettings)}
    unknown = sorted(set(payload) - known)
    if unknown:
        logger.info("Ignoring unknown settings keys: %s", ", ".join(unknown))

    invalid: list[str] = []

    hotkey = _coerce_text(
        payload.get("hotkey", _MISSING), defaults.hotkey, "hotkey", invalid
    )
    model_name = _coerce_text(
        payload.get("model_name", _MISSING), defaults.model_name, "model_name", invalid
    )
    target_mode = _coerce_text(
        payload.get("target_mode", _MISSING),
        defaults.target_mode,
        "target_mode",
        invalid,
    )
    max_duration = _coerce_positive_int(
        payload.get("max_duration_seconds", _MISSING),
        defaults.max_duration_seconds,
        "max_duration_seconds",
        invalid,
    )
    sample_rate = _coerce_positive_int(
        payload.get("sample_rate", _MISSING),
        defaults.sample_rate,
        "sample_rate",
        invalid,
    )
    channels = _coerce_positive_int(
        payload.get("channels", _MISSING), defaults.channels, "channels", invalid
    )
    fallback_to_clipboard = _coerce_bool(
        payload.get("fallback_to_clipboard", _MISSING),
        defaults.fallback_to_clipboard,
        "fallback_to_clipboard",
        invalid,
    )

    if invalid:
        logger.warning(
            "Settings contained invalid values for: %s. Defaults applied.",
            ", ".join(invalid),
        )

    return AppSettings(
        hotkey=hotkey,
        model_name=model_name,
        max_duration_seconds=max_duration,
        sample_rate=sample_rate,
        channels=channels,
        target_mode=target_mode,
        fallback_to_clipboard=fallback_to_clipboard,
    )


def _coerce_text(value: object, default: str, name: str, invalid: list[str]) -> str:
    if value is _MISSING:
        return default
    if not isinstance(value, str) or not value.strip():
        invalid.append(name)
        return default
    return value.strip()


def _coerce_positive_int(
    value: object, default: int, name: str, invalid: list[str]
) -> int:
    if value is _MISSING:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        invalid.append(name)
        return default
    return value


def _coerce_bool(value: object, default: bool, name: str, invalid: list[str]) -> bool:
    if value is _MISSING:
        return default
    if not isinstance(value, bool):
        invalid.append(name)
        return default
    return value


class SettingsStore:
    def __init__(self, paths: AppPaths):
        self._paths = paths

    def load(self) -> AppSettings:
        if not self._paths.settings_path.exists():
            return AppSettings()

        try:
            raw = self._paths.settings_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not read settings file: %s", exc)
            return AppSettings()

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Settings file is not valid JSON (%s); defaults applied", exc
            )
            return AppSettings()

        return settings_from_payload(payload)

    def save(self, settings: AppSettings) -> None:
        self._paths.settings_path.write_text(
            json.dumps(asdict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Settings saved to %s", self._paths.settings_path)

