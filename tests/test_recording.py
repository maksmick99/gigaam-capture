from __future__ import annotations

from pathlib import Path

import pytest

from gigaam_capture.config import build_app_paths, ensure_app_dirs
from gigaam_capture.models import AppSettings
from gigaam_capture.services.recording import RecordingService


class FakeRecorder:
    """Recorder stub that feeds chunks on demand."""

    def __init__(self) -> None:
        self.started_with: tuple[int, int] | None = None
        self.stopped = False
        self._on_chunk = None

    def start(self, *, samplerate: int, channels: int, on_chunk) -> None:
        self.started_with = (samplerate, channels)
        self._on_chunk = on_chunk

    def stop(self) -> None:
        self.stopped = True

    def push(self, frames: int) -> None:
        np = pytest.importorskip("numpy")
        assert self._on_chunk is not None
        self._on_chunk(np.zeros((frames, 1), dtype="float32"))


class BrokenRecorder:
    def start(self, *, samplerate: int, channels: int, on_chunk) -> None:
        raise RuntimeError("no microphone available")

    def stop(self) -> None:  # pragma: no cover - never reached
        pass


def _service(tmp_path: Path) -> tuple[RecordingService, FakeRecorder]:
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    recorder = FakeRecorder()
    settings = AppSettings(sample_rate=8000, max_duration_seconds=2)
    return RecordingService(paths, settings, recorder=recorder), recorder


def test_recording_duration_reflects_captured_frames(tmp_path: Path):
    service, recorder = _service(tmp_path)
    service.start()
    recorder.push(4000)  # 0.5 s at 8 kHz

    result = service.stop()

    assert result.duration_seconds == pytest.approx(0.5)
    assert service.is_recording is False
    assert recorder.stopped


def test_recording_writes_audio_with_captured_length(tmp_path: Path):
    sf = pytest.importorskip("soundfile")
    service, recorder = _service(tmp_path)
    service.start()
    recorder.push(4000)

    result = service.stop()
    data, samplerate = sf.read(result.audio_path)

    assert result.audio_path.exists()
    assert samplerate == 8000
    assert len(data) == 4000


def test_recording_truncates_frames_beyond_the_limit(tmp_path: Path):
    service, recorder = _service(tmp_path)
    service.start()
    recorder.push(50000)

    result = service.stop()

    assert result.duration_seconds == pytest.approx(2.0)


def test_poll_returns_none_until_limit_is_reached(tmp_path: Path):
    service, recorder = _service(tmp_path)
    service.start()
    recorder.push(4000)

    assert service.poll() is None
    assert service.is_recording


def test_poll_stops_recording_at_the_limit(tmp_path: Path):
    service, recorder = _service(tmp_path)
    service.start()
    recorder.push(16000)

    assert service.limit_reached
    result = service.poll()

    assert result is not None
    assert result.duration_seconds == pytest.approx(2.0)
    assert service.is_recording is False


def test_recording_progress_reports_remaining_time(tmp_path: Path):
    service, recorder = _service(tmp_path)
    service.start()
    recorder.push(4000)

    assert service.elapsed_seconds == pytest.approx(0.5)
    assert service.remaining_seconds == pytest.approx(1.5)


def test_start_failure_clears_the_session(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    service = RecordingService(paths, AppSettings(), recorder=BrokenRecorder())

    with pytest.raises(RuntimeError):
        service.start()

    assert service.is_recording is False


def test_stop_without_active_recording_raises(tmp_path: Path):
    service, _ = _service(tmp_path)

    with pytest.raises(RuntimeError):
        service.stop()


def test_settings_update_is_rejected_while_recording(tmp_path: Path):
    service, _ = _service(tmp_path)
    service.start()

    with pytest.raises(RuntimeError):
        service.update_settings(AppSettings())
