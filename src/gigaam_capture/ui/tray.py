from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from gigaam_capture.config import SettingsStore
from gigaam_capture.history import HistoryStore
from gigaam_capture.models import AppPaths, AppSettings, CaptureState, TranscriptionRecord
from gigaam_capture.output_targets import OutputTarget, create_output_target
from gigaam_capture.services.hotkeys import HotkeyService
from gigaam_capture.services.recording import RecordingResult, RecordingService
from gigaam_capture.services.transcription import TranscriptionService
from gigaam_capture.ui.settings_dialog import SettingsDialog


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

    def __init__(
        self,
        paths: AppPaths,
        settings: AppSettings,
        recording_service: Optional[RecordingService] = None,
        transcription_service: Optional[TranscriptionService] = None,
        history_store: Optional[HistoryStore] = None,
        output_target: Optional[OutputTarget] = None,
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
        self._output = output_target or create_output_target(settings.target_mode)
        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[TranscriptionWorker] = None
        self._pending_recording: Optional[RecordingResult] = None
        self.toggle_requested.connect(self.toggle_capture)

    @property
    def state(self) -> CaptureState:
        return self._state

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @Slot()
    def toggle_capture(self) -> None:
        if self._state == "transcribing":
            return

        try:
            if self._recording.is_recording:
                result = self._recording.stop()
                self._pending_recording = result
                self._set_state("transcribing")
                self._launch_transcription(result)
                return

            self._recording.start()
            self._set_state("recording")
        except Exception as exc:
            self._set_state("error")
            self.last_transcription_changed.emit(str(exc))

    def _launch_transcription(self, result: RecordingResult) -> None:
        if self._worker_thread is not None:
            raise RuntimeError("Transcription is already running")

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
        text_path = Path(str(result.audio_path).replace(".wav", ".txt"))
        record = TranscriptionRecord.create(
            audio_path=result.audio_path,
            text_path=text_path,
            model_name=self._transcription.model_name,
            duration_seconds=result.duration_seconds,
            text=text,
            target_mode=self._settings.target_mode,
            target_hint=self._describe_output_target(),
        )
        self._history.append(record)
        self._output.deliver(text)
        self._pending_recording = None
        self.delivery_completed.emit(self._output.name)
        self.last_transcription_changed.emit(text)
        self._set_state("idle")

    @Slot(str)
    def _on_transcription_failed(self, message: str) -> None:
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
        self._settings = settings
        self._recording.update_settings(settings)
        self._transcription.update_settings(settings.model_name)
        self._output = create_output_target(settings.target_mode)

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
        if self._settings.target_mode == "clipboard":
            return "Clipboard target selected; active app inspection is not required"

        describe = getattr(self._output, "describe_target", None)
        if callable(describe):
            return str(describe())

        return f"Target selected: {self._output.name}"


class TrayApplication:
    def __init__(
        self,
        app: QApplication,
        paths: AppPaths,
        settings: AppSettings,
        settings_store: SettingsStore,
    ):
        self._app = app
        self._paths = paths
        self._settings_store = settings_store
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

        self._hotkeys = HotkeyService(settings.hotkey, self._controller.toggle_requested.emit)
        self._refresh_status_action()

    def start(self) -> None:
        self._tray.show()
        self._hotkeys.start()

    def shutdown(self) -> None:
        self._hotkeys.stop()
        self._tray.hide()
        self._app.quit()

    def _on_state_changed(self, state: str) -> None:
        mapping = {
            "idle": "Start recording",
            "recording": "Stop recording",
            "transcribing": "Transcribing...",
            "error": "Retry recording",
        }
        self._toggle_action.setText(mapping.get(state, "Start recording"))
        self._tray.setToolTip(f"GigaAM Capture: {state}")
        target_label = {
            "clipboard": "Transcription is copied to clipboard",
            "active-text-field": "Transcription is pasted into the active text field",
        }
        self._copy_hint_action.setText(
            target_label.get(self._controller.settings.target_mode, "Transcription target selected")
        )
        self._refresh_status_action()

    def _on_last_transcription(self, text: str) -> None:
        self._tray.showMessage(
            "GigaAM Capture",
            text[:180] if text else "No text generated",
            QSystemTrayIcon.MessageIcon.Information,
            4000,
        )

    def _on_delivery_completed(self, output_name: str) -> None:
        message = {
            "clipboard": "Transcript copied to clipboard",
            "active-text-field": "Transcript pasted into the active text field",
        }.get(output_name, f"Transcript delivered via {output_name}")
        self._tray.showMessage(
            "GigaAM Capture",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            2500,
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
                "Finish the current recording or transcription before changing settings.",
            )
            return

        dialog = SettingsDialog(self._controller.settings)
        if dialog.exec() == SettingsDialog.DialogCode.Rejected:
            return

        settings = dialog.get_settings()
        self._settings_store.save(settings)
        self._controller.update_settings(settings)
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
        self._hotkeys.start()

    def _open_path(self, path: Path) -> None:
        opened = QDesktopServicesShim.open_path(path)
        if not opened:
            QMessageBox.warning(None, "GigaAM Capture", f"Could not open {path}")

    def _refresh_status_action(self) -> None:
        settings = self._controller.settings
        target_label = {
            "clipboard": "Clipboard",
            "active-text-field": "Active text field",
        }.get(settings.target_mode, settings.target_mode)
        self._status_action.setText(
            f"Hotkey: {settings.hotkey} | Target: {target_label}"
        )


class QDesktopServicesShim:
    @staticmethod
    def open_path(path: Path) -> bool:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
