from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from gigaam_capture.config import SettingsStore
from gigaam_capture.history import HistoryStore
from gigaam_capture.log import get_logger
from gigaam_capture.models import (
    TARGET_ACTIVE_TEXT_FIELD,
    TARGET_CLIPBOARD,
    AppPaths,
    AppSettings,
    CaptureState,
    DeliveryOutcome,
    TranscriptionRecord,
)
from gigaam_capture.output_targets import (
    ClipboardTarget,
    OutputTarget,
    UnsupportedTargetError,
    create_output_target,
)
from gigaam_capture.services.hotkeys import HotkeyService
from gigaam_capture.services.recording import RecordingResult, RecordingService
from gigaam_capture.services.transcription import TranscriptionService
from gigaam_capture.ui.settings_dialog import SettingsDialog

logger = get_logger("ui.tray")

RECORDING_TICK_MS = 100
TRANSCRIPT_NOTIFICATION_LIMIT = 180
TARGET_LABELS = {
    TARGET_CLIPBOARD: "Clipboard",
    TARGET_ACTIVE_TEXT_FIELD: "Active text field",
}
DELIVERED_MESSAGES = {
    TARGET_CLIPBOARD: "Transcript copied to clipboard",
    TARGET_ACTIVE_TEXT_FIELD: "Transcript pasted into the active text field",
}


class TranscriptionWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, transcription: TranscriptionService, audio_path: Path):
        super().__init__()
        self._transcription = transcription
        self._audio_path = audio_path

    @Slot()
    def run(self) -> None:
        try:
            text = self._transcription.transcribe(self._audio_path)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(text)


class AppController(QObject):
    toggle_requested = Signal()
    state_changed = Signal(str)
    last_transcription_changed = Signal(str)
    delivery_completed = Signal(str)
    delivery_failed = Signal(str)
    recording_progress = Signal(float)

    def __init__(
        self,
        paths: AppPaths,
        settings: AppSettings,
        recording_service: RecordingService | None = None,
        transcription_service: TranscriptionService | None = None,
        history_store: HistoryStore | None = None,
        output_target: OutputTarget | None = None,
    ):
        super().__init__()
        self._paths = paths
        self._settings = settings
        self._state: CaptureState = "idle"
        self._recording = recording_service or RecordingService(paths, settings)
        self._transcription = transcription_service or TranscriptionService(
            settings.model_name
        )
        self._history = history_store or HistoryStore(paths)
        self._output = output_target or self._create_output_target(settings)
        self._worker_thread: QThread | None = None
        self._worker: TranscriptionWorker | None = None
        self._pending_recording: RecordingResult | None = None
        self._timer: QTimer | None = None
        self.toggle_requested.connect(self.toggle_capture)

    def _create_output_target(self, settings: AppSettings) -> OutputTarget:
        try:
            return create_output_target(settings.target_mode)
        except UnsupportedTargetError as exc:
            logger.warning("Falling back to clipboard delivery: %s", exc)
            return ClipboardTarget()

    @property
    def state(self) -> CaptureState:
        return self._state

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @Slot()
    def toggle_capture(self) -> None:
        if self._state == "transcribing":
            logger.info("Capture toggle ignored while transcription is running")
            return

        try:
            if self._recording.is_recording:
                self._finish_recording(self._recording.stop())
                return

            self._recording.start()
            self._set_state("recording")
            self._start_progress_timer()
        except Exception as exc:
            logger.exception("Capture toggle failed")
            self._set_state("error")
            self.last_transcription_changed.emit(str(exc))

    def _finish_recording(self, result: RecordingResult) -> None:
        self._stop_progress_timer()
        self._pending_recording = result
        self._set_state("transcribing")
        self._launch_transcription(result)

    def _start_progress_timer(self) -> None:
        if QCoreApplication.instance() is None:
            logger.debug("No Qt application instance; recording progress is disabled")
            return
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setInterval(RECORDING_TICK_MS)
            self._timer.timeout.connect(self._on_recording_tick)
        self._timer.start()

    def _stop_progress_timer(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    @Slot()
    def _on_recording_tick(self) -> None:
        if self._state != "recording":
            self._stop_progress_timer()
            return

        remaining = getattr(self._recording, "remaining_seconds", None)
        if isinstance(remaining, (int, float)):
            self.recording_progress.emit(float(remaining))

        poll = getattr(self._recording, "poll", None)
        if not callable(poll):
            return

        try:
            result = poll()
        except Exception as exc:
            logger.exception("Recording poll failed")
            self._stop_progress_timer()
            self._set_state("error")
            self.last_transcription_changed.emit(str(exc))
            return

        if result is not None:
            logger.info("Recording stopped automatically at the duration limit")
            self._finish_recording(result)

    def _launch_transcription(self, result: RecordingResult) -> None:
        if self._worker_thread is not None:
            raise RuntimeError("Transcription is already running")

        logger.info("Starting transcription for %s", result.audio_path)
        self._worker_thread = QThread(self)
        self._worker = TranscriptionWorker(self._transcription, result.audio_path)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_transcription_completed)
        self._worker.failed.connect(self._on_transcription_failed)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.failed.connect(self._cleanup_worker)
        self._worker_thread.start()

    @Slot(str)
    def _on_transcription_completed(self, text: str) -> None:
        if self._pending_recording is None:
            self._set_state("error")
            self.last_transcription_changed.emit("Missing recording context")
            return

        result = self._pending_recording
        outcome = self._deliver_transcript(text)
        self._store_history(result, text, outcome)
        self._pending_recording = None

        if not outcome.delivered:
            self.delivery_failed.emit(outcome.message)
            self._set_state("error")
            return

        self.delivery_completed.emit(outcome.status)
        self.last_transcription_changed.emit(text)
        self._set_state("idle")

    def _deliver_transcript(self, text: str) -> DeliveryOutcome:
        try:
            self._output.deliver(text)
        except Exception as exc:
            logger.warning("Delivery via %s failed: %s", self._output.name, exc)
            return self._fallback_delivery(text, exc)

        logger.info("Transcript delivered via %s", self._output.name)
        return DeliveryOutcome(
            target_name=self._output.name,
            status="delivered",
            message=DELIVERED_MESSAGES.get(
                self._output.name, f"Transcript delivered via {self._output.name}"
            ),
        )

    def _fallback_delivery(self, text: str, error: Exception) -> DeliveryOutcome:
        target_name = self._output.name
        label = TARGET_LABELS.get(target_name, target_name)
        if not self._settings.fallback_to_clipboard or target_name == TARGET_CLIPBOARD:
            return DeliveryOutcome(
                target_name=target_name,
                status="failed",
                message=f"{label} delivery failed: {error}",
            )

        try:
            ClipboardTarget().deliver(text)
        except Exception as clipboard_error:
            logger.exception("Clipboard fallback failed")
            return DeliveryOutcome(
                target_name=target_name,
                status="failed",
                message=(
                    f"{label} delivery failed: {error}. "
                    f"Clipboard fallback also failed: {clipboard_error}"
                ),
            )

        logger.info("%s delivery failed; transcript copied to clipboard", target_name)
        return DeliveryOutcome(
            target_name=TARGET_CLIPBOARD,
            status="fallback-clipboard",
            message=(
                f"{label} delivery failed: {error} "
                "The transcript was copied to the clipboard instead."
            ),
        )

    def _store_history(
        self, result: RecordingResult, text: str, outcome: DeliveryOutcome
    ) -> None:
        text_path = Path(result.audio_path).with_suffix(".txt")
        record = TranscriptionRecord.create(
            audio_path=result.audio_path,
            text_path=text_path,
            model_name=self._transcription.model_name,
            duration_seconds=result.duration_seconds,
            text=text,
            target_mode=self._settings.target_mode,
            target_hint=self._describe_output_target(),
            delivery_status=outcome.status,
        )
        try:
            self._history.append(record)
        except OSError as exc:
            logger.warning("Could not write history entry: %s", exc)

    @Slot(str)
    def _on_transcription_failed(self, message: str) -> None:
        logger.warning("Transcription failed: %s", message)
        self._pending_recording = None
        self._set_state("error")
        self.last_transcription_changed.emit(message)

    @Slot()
    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread.deleteLater()
            self._worker_thread = None

    def update_settings(self, settings: AppSettings) -> None:
        if self._state != "idle":
            raise RuntimeError("Settings can only be updated while the app is idle")

        # Build the target first so a rejected mode leaves the controller as-is.
        output_target = create_output_target(settings.target_mode)
        self._settings = settings
        self._recording.update_settings(settings)
        self._transcription.update_settings(settings.model_name)
        self._output = output_target
        logger.info(
            "Settings applied: target=%s hotkey=%s model=%s",
            settings.target_mode,
            settings.hotkey,
            settings.model_name,
        )

    def _set_state(self, state: CaptureState) -> None:
        self._state = state
        self.state_changed.emit(state)

    def _describe_output_target(self) -> str:
        describe = getattr(self._output, "describe_target", None)
        if callable(describe):
            try:
                return str(describe())
            except Exception:
                return self._output.name
        return self._output.name

    def inspect_active_target_context(self) -> str:
        if self._settings.target_mode == TARGET_CLIPBOARD:
            return "Clipboard target selected; active app inspection is not required"

        describe = getattr(self._output, "describe_target", None)
        if callable(describe):
            return str(describe())

        return f"Target selected: {self._output.name}"

    def shutdown(self) -> None:
        """Release runtime resources, discarding an in-flight capture."""
        self._stop_progress_timer()

        if not self._recording.is_recording:
            return

        try:
            result = self._recording.stop()
        except Exception:
            logger.exception("Could not stop the active recording during shutdown")
            return

        logger.warning(
            "Discarded an active recording on shutdown; audio kept at %s",
            result.audio_path,
        )


class TrayApplication:
    def __init__(
        self,
        app: QApplication,
        paths: AppPaths,
        settings: AppSettings,
        settings_store: SettingsStore,
        startup_notice: str | None = None,
    ):
        self._app = app
        self._paths = paths
        self._settings_store = settings_store
        self._startup_notice = startup_notice
        self._controller = AppController(paths, settings)
        self._tray = QSystemTrayIcon(QIcon())
        self._menu = QMenu()
        self._status_action = QAction()
        self._status_action.setEnabled(False)
        self._toggle_action = QAction("Start recording")
        self._copy_hint_action = QAction("Transcription is copied to clipboard")
        self._copy_hint_action.setEnabled(False)
        self._inspect_target_action = QAction("Inspect active target")
        self._settings_action = QAction("Settings")
        self._open_history_action = QAction("Open history folder")
        self._quit_action = QAction("Quit")

        self._toggle_action.triggered.connect(self._controller.toggle_capture)
        self._inspect_target_action.triggered.connect(self._inspect_active_target)
        self._settings_action.triggered.connect(self._open_settings)
        self._open_history_action.triggered.connect(
            lambda: self._open_path(paths.history_dir)
        )
        self._quit_action.triggered.connect(self.shutdown)

        self._menu.addAction(self._status_action)
        self._menu.addAction(self._toggle_action)
        self._menu.addAction(self._copy_hint_action)
        self._menu.addAction(self._inspect_target_action)
        self._menu.addAction(self._settings_action)
        self._menu.addSeparator()
        self._menu.addAction(self._open_history_action)
        self._menu.addAction(self._quit_action)
        self._tray.setContextMenu(self._menu)
        self._tray.setToolTip("GigaAM Capture")

        self._controller.state_changed.connect(self._on_state_changed)
        self._controller.last_transcription_changed.connect(self._on_last_transcription)
        self._controller.delivery_completed.connect(self._on_delivery_completed)
        self._controller.delivery_failed.connect(self._on_delivery_failed)
        self._controller.recording_progress.connect(self._on_recording_progress)

        self._hotkeys = HotkeyService(
            settings.hotkey, self._controller.toggle_requested.emit
        )
        self._refresh_status_action()

    def start(self) -> None:
        self._tray.show()

        if self._startup_notice:
            self._tray.showMessage(
                "GigaAM Capture",
                self._startup_notice,
                QSystemTrayIcon.MessageIcon.Warning,
                8000,
            )

        self._register_hotkeys()

    def shutdown(self) -> None:
        self._hotkeys.stop()
        self._controller.shutdown()
        self._tray.hide()
        self._app.quit()

    def _register_hotkeys(self) -> None:
        try:
            self._hotkeys.start()
        except ValueError as exc:
            logger.warning("Global hotkey is not usable: %s", exc)
            self._tray.showMessage(
                "GigaAM Capture",
                f"{exc} Use the tray menu until the hotkey is fixed in Settings.",
                QSystemTrayIcon.MessageIcon.Warning,
                8000,
            )

    def _on_state_changed(self, state: str) -> None:
        mapping = {
            "idle": "Start recording",
            "recording": "Stop recording",
            "transcribing": "Transcribing...",
            "error": "Retry recording",
        }
        self._toggle_action.setText(mapping.get(state, "Start recording"))
        self._tray.setToolTip(f"GigaAM Capture: {state}")
        self._copy_hint_action.setText(
            DELIVERED_MESSAGES.get(
                self._controller.settings.target_mode, "Transcription target selected"
            )
        )
        self._refresh_status_action()

    def _on_last_transcription(self, text: str) -> None:
        self._tray.showMessage(
            "GigaAM Capture",
            text[:TRANSCRIPT_NOTIFICATION_LIMIT] if text else "No text generated",
            QSystemTrayIcon.MessageIcon.Information,
            4000,
        )

    def _on_delivery_completed(self, status: str) -> None:
        if status == "fallback-clipboard":
            message = (
                "Active text field delivery failed; transcript copied to clipboard"
            )
            icon = QSystemTrayIcon.MessageIcon.Warning
            timeout = 5000
        else:
            target_mode = self._controller.settings.target_mode
            message = DELIVERED_MESSAGES.get(
                target_mode, f"Transcript delivered via {target_mode}"
            )
            icon = QSystemTrayIcon.MessageIcon.Information
            timeout = 2500

        self._tray.showMessage("GigaAM Capture", message, icon, timeout)

    def _on_delivery_failed(self, message: str) -> None:
        self._tray.showMessage(
            "GigaAM Capture",
            message[:240] if message else "Transcript delivery failed",
            QSystemTrayIcon.MessageIcon.Critical,
            6000,
        )

    def _on_recording_progress(self, remaining_seconds: float) -> None:
        seconds = max(0, int(round(remaining_seconds)))
        self._tray.setToolTip(f"GigaAM Capture: recording, {seconds}s left")
        self._status_action.setText(
            f"Recording... {seconds}s left | Hotkey: {self._controller.settings.hotkey}"
        )

    def _inspect_active_target(self) -> None:
        try:
            message = self._controller.inspect_active_target_context()
            icon = QSystemTrayIcon.MessageIcon.Information
        except Exception as exc:
            message = str(exc)
            icon = QSystemTrayIcon.MessageIcon.Warning

        self._tray.showMessage(
            "GigaAM Capture",
            message[:240] if message else "No target information available",
            icon,
            4500,
        )

    def _open_settings(self) -> None:
        if self._controller.state != "idle":
            QMessageBox.information(
                None,
                "GigaAM Capture",
                "Finish the current recording or transcription "
                "before changing settings.",
            )
            return

        dialog = SettingsDialog(self._controller.settings)
        if dialog.exec() == SettingsDialog.DialogCode.Rejected:
            return

        settings = dialog.get_settings()
        try:
            self._controller.update_settings(settings)
        except (UnsupportedTargetError, RuntimeError) as exc:
            logger.warning("Rejected settings update: %s", exc)
            QMessageBox.warning(None, "GigaAM Capture", str(exc))
            return

        try:
            self._settings_store.save(settings)
        except OSError as exc:
            logger.warning("Could not persist settings: %s", exc)
            QMessageBox.warning(
                None,
                "GigaAM Capture",
                f"Settings are active for this session but could not be saved: {exc}",
            )

        self._restart_hotkeys(settings.hotkey)
        self._refresh_status_action()
        self._tray.showMessage(
            "GigaAM Capture",
            "Settings saved",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _restart_hotkeys(self, hotkey: str) -> None:
        self._hotkeys.stop()
        self._hotkeys = HotkeyService(hotkey, self._controller.toggle_requested.emit)
        self._register_hotkeys()

    def _open_path(self, path: Path) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(None, "GigaAM Capture", f"Could not open {path}")

    def _refresh_status_action(self) -> None:
        settings = self._controller.settings
        target_label = TARGET_LABELS.get(settings.target_mode, settings.target_mode)
        self._status_action.setText(
            f"Hotkey: {settings.hotkey} | Target: {target_label}"
        )
