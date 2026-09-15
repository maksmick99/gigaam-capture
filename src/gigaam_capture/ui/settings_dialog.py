from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from gigaam_capture.models import TARGET_CLIPBOARD, AppSettings
from gigaam_capture.platform import target_capabilities
from gigaam_capture.services.hotkeys import validate_hotkey

# ASR-capable GigaAM model versions. SSL and emotion checkpoints are
# intentionally excluded because they do not expose `transcribe()`.
AVAILABLE_MODELS = [
    "v3_e2e_rnnt",
    "v3_e2e_ctc",
    "v3_rnnt",
    "v3_ctc",
    "v2_rnnt",
    "v2_ctc",
    "v1_rnnt",
    "v1_ctc",
    "multilingual_ctc",
    "multilingual_large_ctc",
]


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GigaAM Capture Settings")

        self._hotkey = QLineEdit(settings.hotkey)
        self._model = QComboBox()
        self._model.addItems(AVAILABLE_MODELS)
        if settings.model_name not in AVAILABLE_MODELS:
            self._model.addItem(settings.model_name)
        self._model.setCurrentText(settings.model_name)

        self._max_duration = QSpinBox()
        self._max_duration.setRange(1, 25)
        self._max_duration.setValue(settings.max_duration_seconds)

        self._sample_rate = QSpinBox()
        self._sample_rate.setRange(8000, 48000)
        self._sample_rate.setSingleStep(1000)
        self._sample_rate.setValue(settings.sample_rate)

        self._channels = QSpinBox()
        self._channels.setRange(1, 2)
        self._channels.setValue(settings.channels)

        capabilities = target_capabilities()
        available_targets = [item.mode for item in capabilities if item.available]
        self._target = QComboBox()
        self._target.addItems(available_targets)
        if settings.target_mode in available_targets:
            self._target.setCurrentText(settings.target_mode)
        else:
            self._target.setCurrentText(TARGET_CLIPBOARD)

        self._fallback = QCheckBox(
            "Copy the transcript to the clipboard when active text-field delivery fails"
        )
        self._fallback.setChecked(settings.fallback_to_clipboard)

        form = QFormLayout()
        form.addRow("Hotkey", self._hotkey)
        form.addRow("Model", self._model)
        form.addRow("Max duration (sec)", self._max_duration)
        form.addRow("Sample rate", self._sample_rate)
        form.addRow("Channels", self._channels)
        form.addRow("Output mode", self._target)

        unavailable = [
            f"{item.mode}: {item.reason}"
            for item in capabilities
            if not item.available and item.reason
        ]
        if unavailable:
            note = QLabel("\n".join(unavailable))
            note.setWordWrap(True)
            form.addRow("Unavailable here", note)

        form.addRow("", self._fallback)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def accept(self) -> None:
        problem = validate_hotkey(self._hotkey.text())
        if problem is not None:
            QMessageBox.warning(self, "GigaAM Capture", problem)
            return
        super().accept()

    def get_settings(self) -> AppSettings:
        return AppSettings(
            hotkey=self._hotkey.text().strip(),
            model_name=self._model.currentText(),
            max_duration_seconds=self._max_duration.value(),
            sample_rate=self._sample_rate.value(),
            channels=self._channels.value(),
            target_mode=self._target.currentText(),
            fallback_to_clipboard=self._fallback.isChecked(),
        )