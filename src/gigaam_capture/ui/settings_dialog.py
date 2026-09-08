from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from gigaam_capture.models import AppSettings

AVAILABLE_MODELS = [
    "v3_e2e_rnnt",
    "v3_e2e_ctc",
    "v3_rnnt",
    "v3_ctc",
    "v2_ssl",
    "v3_ssl",
    "emo",
]

AVAILABLE_TARGETS = ["clipboard", "active-text-field"]


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GigaAM Capture Settings")

        self._hotkey = QLineEdit(settings.hotkey)
        self._model = QComboBox()
        self._model.addItems(AVAILABLE_MODELS)
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

        self._target = QComboBox()
        self._target.addItems(AVAILABLE_TARGETS)
        self._target.setCurrentText(settings.target_mode)

        form = QFormLayout()
        form.addRow("Hotkey", self._hotkey)
        form.addRow("Model", self._model)
        form.addRow("Max duration (sec)", self._max_duration)
        form.addRow("Sample rate", self._sample_rate)
        form.addRow("Channels", self._channels)
        form.addRow("Output mode", self._target)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_settings(self) -> AppSettings:
        return AppSettings(
            hotkey=self._hotkey.text().strip() or "<cmd>+<shift>+r",
            model_name=self._model.currentText(),
            max_duration_seconds=self._max_duration.value(),
            sample_rate=self._sample_rate.value(),
            channels=self._channels.value(),
            target_mode=self._target.currentText(),
        )