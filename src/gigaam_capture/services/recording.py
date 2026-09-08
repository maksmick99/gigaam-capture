from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import sounddevice as sd
import soundfile as sf

from gigaam_capture.models import AppPaths, AppSettings, CaptureSession


@dataclass(slots=True)
class RecordingResult:
    audio_path: Path
    duration_seconds: float


class RecordingService:
    def __init__(self, paths: AppPaths, settings: AppSettings):
        self._paths = paths
        self._settings = settings
        self._recording = None
        self._session: CaptureSession | None = None

    def update_settings(self, settings: AppSettings) -> None:
        if self.is_recording:
            raise RuntimeError("Cannot update recording settings during an active capture")
        self._settings = settings

    @property
    def is_recording(self) -> bool:
        return self._session is not None

    def start(self) -> CaptureSession:
        if self._session is not None:
            raise RuntimeError("Recording is already active")

        started_at = datetime.now(timezone.utc)
        audio_path = self._paths.recordings_dir / f"{started_at.strftime('%Y%m%dT%H%M%SZ')}.wav"
        frames = self._settings.max_duration_seconds * self._settings.sample_rate
        self._recording = sd.rec(
            frames,
            samplerate=self._settings.sample_rate,
            channels=self._settings.channels,
            dtype="float32",
        )
        self._session = CaptureSession(audio_path=audio_path, started_at=started_at)
        return self._session

    def stop(self) -> RecordingResult:
        if self._session is None or self._recording is None:
            raise RuntimeError("Recording is not active")

        sd.stop()
        sd.wait()
        duration_seconds = len(self._recording) / self._settings.sample_rate
        sf.write(
            self._session.audio_path,
            self._recording,
            self._settings.sample_rate,
        )
        result = RecordingResult(
            audio_path=self._session.audio_path,
            duration_seconds=duration_seconds,
        )
        self._recording = None
        self._session = None
        return result
