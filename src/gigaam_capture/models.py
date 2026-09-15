from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

CaptureState = Literal["idle", "recording", "transcribing", "error"]

TARGET_CLIPBOARD = "clipboard"
TARGET_ACTIVE_TEXT_FIELD = "active-text-field"

DeliveryStatus = Literal["delivered", "fallback-clipboard", "failed"]


def default_hotkey() -> str:
    """Return the platform-appropriate default global hotkey.

    macOS keeps the Command-based combination, while Windows and Linux use
    Ctrl+Alt+R so the default does not collide with the ``Win+R`` system
    shortcut.
    """
    if sys.platform == "darwin":
        return "<cmd>+<shift>+r"
    return "<ctrl>+<alt>+r"


@dataclass(slots=True)
class AppPaths:
    root: Path
    history_dir: Path
    recordings_dir: Path
    history_log: Path
    settings_path: Path
    log_path: Path


@dataclass(slots=True)
class AppSettings:
    hotkey: str = field(default_factory=default_hotkey)
    model_name: str = "v3_e2e_rnnt"
    max_duration_seconds: int = 25
    sample_rate: int = 16000
    channels: int = 1
    target_mode: str = TARGET_CLIPBOARD
    fallback_to_clipboard: bool = True


@dataclass(slots=True)
class CaptureSession:
    audio_path: Path
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class DeliveryOutcome:
    target_name: str
    status: DeliveryStatus
    message: str

    @property
    def delivered(self) -> bool:
        return self.status != "failed"


@dataclass(slots=True)
class TranscriptionRecord:
    identifier: str
    created_at: str
    audio_path: str
    text_path: str
    model_name: str
    duration_seconds: float
    text: str
    target_mode: str
    target_hint: str | None = None
    delivery_status: str | None = None

    @classmethod
    def create(
        cls,
        *,
        audio_path: Path,
        text_path: Path,
        model_name: str,
        duration_seconds: float,
        text: str,
        target_mode: str,
        target_hint: str | None = None,
        delivery_status: str | None = None,
    ) -> TranscriptionRecord:
        created_at = datetime.now(timezone.utc)
        return cls(
            identifier=uuid4().hex,
            created_at=created_at.isoformat(),
            audio_path=str(audio_path),
            text_path=str(text_path),
            model_name=model_name,
            duration_seconds=duration_seconds,
            text=text,
            target_mode=target_mode,
            target_hint=target_hint,
            delivery_status=delivery_status,
        )
