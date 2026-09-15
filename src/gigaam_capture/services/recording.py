from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from gigaam_capture.log import get_logger
from gigaam_capture.models import AppPaths, AppSettings, CaptureSession

logger = get_logger("services.recording")


@dataclass(slots=True)
class RecordingResult:
    audio_path: Path
    duration_seconds: float


class MicrophoneRecorder(Protocol):
    """Minimal recorder interface so the service can be tested headlessly."""

    def start(
        self,
        *,
        samplerate: int,
        channels: int,
        on_chunk: Callable[[Any], None],
    ) -> None:
        ...

    def stop(self) -> None:
        ...


class SoundDeviceRecorder:
    """Default recorder backed by ``sounddevice``."""

    def __init__(self) -> None:
        self._stream: Any = None

    def start(
        self,
        *,
        samplerate: int,
        channels: int,
        on_chunk: Callable[[Any], None],
    ) -> None:
        import sounddevice as sd

        def _callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            on_chunk(indata.copy())

        self._stream = sd.InputStream(
            samplerate=samplerate,
            channels=channels,
            dtype="float32",
            callback=_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is None:
            return
        stream.stop()
        stream.close()


class RecordingService:
    def __init__(
        self,
        paths: AppPaths,
        settings: AppSettings,
        recorder: MicrophoneRecorder | None = None,
    ):
        self._paths = paths
        self._settings = settings
        self._recorder = recorder or SoundDeviceRecorder()
        self._chunks: list[Any] = []
        self._frames = 0
        self._limit_frames = 0
        self._session: CaptureSession | None = None

    def update_settings(self, settings: AppSettings) -> None:
        if self.is_recording:
            raise RuntimeError(
                "Cannot update recording settings during an active capture"
            )
        self._settings = settings

    @property
    def is_recording(self) -> bool:
        return self._session is not None

    @property
    def elapsed_seconds(self) -> float:
        if self._settings.sample_rate <= 0:
            return 0.0
        return self._frames / self._settings.sample_rate

    @property
    def remaining_seconds(self) -> float:
        limit = self._settings.max_duration_seconds
        remaining = limit - self.elapsed_seconds
        return remaining if remaining > 0 else 0.0

    @property
    def limit_reached(self) -> bool:
        return self._session is not None and self._frames >= self._limit_frames

    def start(self) -> CaptureSession:
        if self._session is not None:
            raise RuntimeError("Recording is already active")

        started_at = datetime.now(timezone.utc)
        audio_path = (
            self._paths.recordings_dir / f"{started_at.strftime('%Y%m%dT%H%M%SZ')}.wav"
        )
        self._chunks = []
        self._frames = 0
        self._limit_frames = (
            self._settings.max_duration_seconds * self._settings.sample_rate
        )
        self._session = CaptureSession(audio_path=audio_path, started_at=started_at)

        try:
            self._recorder.start(
                samplerate=self._settings.sample_rate,
                channels=self._settings.channels,
                on_chunk=self._on_chunk,
            )
        except Exception:
            self._session = None
            self._chunks = []
            self._frames = 0
            raise

        logger.info(
            "Recording started (%s Hz, %s channel(s), limit %ss)",
            self._settings.sample_rate,
            self._settings.channels,
            self._settings.max_duration_seconds,
        )
        return self._session

    def poll(self) -> RecordingResult | None:
        """Return a finished capture when the configured limit has been reached."""
        if self._session is None or not self.limit_reached:
            return None
        logger.info("Recording reached the configured duration limit")
        return self.stop()

    def stop(self) -> RecordingResult:
        if self._session is None:
            raise RuntimeError("Recording is not active")

        session = self._session
        try:
            self._recorder.stop()
        finally:
            self._session = None

        duration_seconds = self.elapsed_seconds
        samples = self._collected_samples()
        self._write_audio(session.audio_path, samples)

        result = RecordingResult(
            audio_path=session.audio_path,
            duration_seconds=duration_seconds,
        )
        self._chunks = []
        self._frames = 0
        logger.info(
            "Recording stopped after %.2fs -> %s", duration_seconds, session.audio_path
        )
        return result

    def _on_chunk(self, chunk: Any) -> None:
        if self._session is None or self._limit_frames <= 0:
            return

        remaining = self._limit_frames - self._frames
        if remaining <= 0:
            return

        available = getattr(chunk, "shape", None)
        rows = int(available[0]) if available else 0
        if rows > remaining:
            chunk = chunk[:remaining]
            rows = remaining
        if rows <= 0:
            return

        self._chunks.append(chunk)
        self._frames += rows

    def _collected_samples(self) -> Any:
        import numpy as np

        if not self._chunks:
            return np.zeros((0, self._settings.channels), dtype="float32")
        return np.concatenate(self._chunks, axis=0)

    def _write_audio(self, audio_path: Path, samples: Any) -> None:
        import soundfile as sf

        sf.write(audio_path, samples, self._settings.sample_rate)

