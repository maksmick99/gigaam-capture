from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from platformdirs import user_data_dir

from .models import AppPaths, AppSettings

APP_NAME = "GigaAM Capture"
APP_AUTHOR = "GigaAM"


def build_app_paths(base_dir: Path | None = None) -> AppPaths:
    root = base_dir or Path(user_data_dir(APP_NAME, APP_AUTHOR))
    history_dir = root / "history"
    recordings_dir = history_dir / "recordings"
    settings_path = root / "settings.json"
    history_log = history_dir / "history.jsonl"
    return AppPaths(
        root=root,
        history_dir=history_dir,
        recordings_dir=recordings_dir,
        history_log=history_log,
        settings_path=settings_path,
    )


def ensure_app_dirs(paths: AppPaths) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.history_dir.mkdir(parents=True, exist_ok=True)
    paths.recordings_dir.mkdir(parents=True, exist_ok=True)


class SettingsStore:
    def __init__(self, paths: AppPaths):
        self._paths = paths

    def load(self) -> AppSettings:
        if not self._paths.settings_path.exists():
            return AppSettings()
        payload = json.loads(self._paths.settings_path.read_text(encoding="utf-8"))
        return AppSettings(**payload)

    def save(self, settings: AppSettings) -> None:
        self._paths.settings_path.write_text(
            json.dumps(asdict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
