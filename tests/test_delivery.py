from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from gigaam_capture.models import (
    TARGET_ACTIVE_TEXT_FIELD,
    TARGET_CLIPBOARD,
    AppSettings,
)
from gigaam_capture.services.recording import RecordingResult
from gigaam_capture.ui.tray import AppController, TrayApplication


class FakeRecordingService:
    def __init__(self) -> None:
        self._active = False
        self.settings = None

    @property
    def is_recording(self) -> bool:
        return self._active

    def update_settings(self, settings) -> None:
        self.settings = settings

    def start(self) -> None:
        self._active = True

    def stop(self):
        raise AssertionError("stop is not used in these tests")


class FakeTranscriptionService:
    model_name = "v3_e2e_rnnt"

    def update_settings(self, model_name: str) -> None:
        self.model_name = model_name


class FakeHistory:
    def __init__(self) -> None:
        self.records = []

    def append(self, record) -> None:
        self.records.append(record)


class FailingTarget:
    name = TARGET_ACTIVE_TEXT_FIELD

    def deliver(self, text: str) -> None:
        raise RuntimeError("Accessibility permission is missing")

    def describe_target(self) -> str:
        return "Telegram | Chat with Alice | AXTextArea"


class WorkingTarget:
    name = TARGET_ACTIVE_TEXT_FIELD

    def __init__(self) -> None:
        self.delivered: list[str] = []

    def deliver(self, text: str) -> None:
        self.delivered.append(text)

    def describe_target(self) -> str:
        return "Telegram | Chat with Alice | AXTextArea"


class FakeClipboardTarget:
    def __init__(self) -> None:
        self.delivered: list[str] = []

    def deliver(self, text: str) -> None:
        self.delivered.append(text)


class BrokenClipboardTarget:
    def deliver(self, text: str) -> None:
        raise RuntimeError("clipboard is locked")


class FakeTrayIcon:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.tooltips: list[str] = []

    def showMessage(self, title, message, icon, timeout) -> None:
        self.calls.append((title, message, icon, timeout))

    def setToolTip(self, text: str) -> None:
        self.tooltips.append(text)


class FakeAction:
    def __init__(self) -> None:
        self._text = ""

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


def _controller(app_paths, settings, target, history=None) -> AppController:
    return AppController(
        app_paths,
        settings,
        recording_service=FakeRecordingService(),
        transcription_service=FakeTranscriptionService(),
        history_store=history or FakeHistory(),
        output_target=target,
    )


def _pending(app_paths) -> RecordingResult:
    return RecordingResult(
        audio_path=app_paths.recordings_dir / "sample.wav",
        duration_seconds=2.5,
    )


def test_successful_delivery_returns_to_idle(app_paths):
    settings = AppSettings(target_mode=TARGET_ACTIVE_TEXT_FIELD)
    target = WorkingTarget()
    history = FakeHistory()
    controller = _controller(app_paths, settings, target, history)
    controller._pending_recording = _pending(app_paths)
    statuses: list[str] = []
    failures: list[str] = []
    controller.delivery_completed.connect(statuses.append)
    controller.delivery_failed.connect(failures.append)

    controller._on_transcription_completed("hello")

    assert target.delivered == ["hello"]
    assert statuses == ["delivered"]
    assert failures == []
    assert controller.state == "idle"
    assert history.records[0].delivery_status == "delivered"


def test_delivery_failure_falls_back_to_clipboard(app_paths):
    settings = AppSettings(target_mode=TARGET_ACTIVE_TEXT_FIELD)
    history = FakeHistory()
    controller = _controller(app_paths, settings, FailingTarget(), history)
    controller._pending_recording = _pending(app_paths)
    statuses: list[str] = []
    failures: list[str] = []
    transcripts: list[str] = []
    controller.delivery_completed.connect(statuses.append)
    controller.delivery_failed.connect(failures.append)
    controller.last_transcription_changed.connect(transcripts.append)
    clipboard = FakeClipboardTarget()

    with patch("gigaam_capture.ui.tray.ClipboardTarget", return_value=clipboard):
        controller._on_transcription_completed("hello")

    assert clipboard.delivered == ["hello"]
    assert statuses == ["fallback-clipboard"]
    assert failures == []
    assert transcripts == ["hello"]
    assert controller.state == "idle"
    assert history.records[0].delivery_status == "fallback-clipboard"
    assert history.records[0].target_hint == "Telegram | Chat with Alice | AXTextArea"


def test_delivery_failure_reports_error_when_fallback_is_disabled(app_paths):
    settings = AppSettings(
        target_mode=TARGET_ACTIVE_TEXT_FIELD,
        fallback_to_clipboard=False,
    )
    history = FakeHistory()
    controller = _controller(app_paths, settings, FailingTarget(), history)
    controller._pending_recording = _pending(app_paths)
    statuses: list[str] = []
    failures: list[str] = []
    controller.delivery_completed.connect(statuses.append)
    controller.delivery_failed.connect(failures.append)

    with patch("gigaam_capture.ui.tray.ClipboardTarget") as clipboard_class:
        controller._on_transcription_completed("hello")

    clipboard_class.assert_not_called()
    assert statuses == []
    assert len(failures) == 1
    assert "Active text field delivery failed" in failures[0]
    assert controller.state == "error"
    assert history.records[0].delivery_status == "failed"


def test_delivery_failure_reports_when_clipboard_fallback_also_fails(app_paths):
    settings = AppSettings(target_mode=TARGET_ACTIVE_TEXT_FIELD)
    controller = _controller(app_paths, settings, FailingTarget())
    controller._pending_recording = _pending(app_paths)
    failures: list[str] = []
    controller.delivery_failed.connect(failures.append)

    with patch(
        "gigaam_capture.ui.tray.ClipboardTarget", return_value=BrokenClipboardTarget()
    ):
        controller._on_transcription_completed("hello")

    assert len(failures) == 1
    assert "Clipboard fallback also failed" in failures[0]
    assert controller.state == "error"


def test_controller_accepts_a_new_capture_after_delivery_failure(app_paths):
    settings = AppSettings(
        target_mode=TARGET_ACTIVE_TEXT_FIELD,
        fallback_to_clipboard=False,
    )
    controller = _controller(app_paths, settings, FailingTarget())
    controller._pending_recording = _pending(app_paths)

    controller._on_transcription_completed("hello")
    assert controller.state == "error"

    controller.toggle_capture()

    assert controller.state == "recording"


def test_tray_reports_fallback_delivery_as_warning():
    tray = TrayApplication.__new__(TrayApplication)
    tray._controller = SimpleNamespace(
        settings=AppSettings(target_mode=TARGET_ACTIVE_TEXT_FIELD)
    )
    tray._tray = FakeTrayIcon()

    TrayApplication._on_delivery_completed(tray, "fallback-clipboard")

    assert tray._tray.calls
    assert "clipboard" in tray._tray.calls[-1][1].lower()


def test_tray_reports_plain_delivery_from_current_target():
    tray = TrayApplication.__new__(TrayApplication)
    tray._controller = SimpleNamespace(
        settings=AppSettings(target_mode=TARGET_CLIPBOARD)
    )
    tray._tray = FakeTrayIcon()

    TrayApplication._on_delivery_completed(tray, "delivered")

    assert tray._tray.calls[-1][1] == "Transcript copied to clipboard"


def test_tray_reports_delivery_failure_as_error():
    tray = TrayApplication.__new__(TrayApplication)
    tray._controller = SimpleNamespace(settings=AppSettings())
    tray._tray = FakeTrayIcon()

    TrayApplication._on_delivery_failed(tray, "Active text field delivery failed: nope")

    assert tray._tray.calls[-1][1] == "Active text field delivery failed: nope"


def test_tray_progress_updates_tooltip_and_status():
    tray = TrayApplication.__new__(TrayApplication)
    tray._controller = SimpleNamespace(settings=AppSettings(hotkey="<ctrl>+<alt>+r"))
    tray._tray = FakeTrayIcon()
    tray._status_action = FakeAction()

    TrayApplication._on_recording_progress(tray, 4.4)

    assert "4s left" in tray._status_action.text()
    assert "4s left" in tray._tray.tooltips[-1]
