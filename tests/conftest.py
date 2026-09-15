from __future__ import annotations

from pathlib import Path

import pytest

from gigaam_capture.config import build_app_paths, ensure_app_dirs
from gigaam_capture.models import AppSettings


@pytest.fixture()
def app_paths(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    return paths


@pytest.fixture()
def settings() -> AppSettings:
    return AppSettings()
