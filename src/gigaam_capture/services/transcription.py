from __future__ import annotations

from pathlib import Path

import gigaam


class TranscriptionService:
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def update_settings(self, model_name: str) -> None:
        if model_name == self._model_name:
            return
        self._model_name = model_name
        self._model = None

    def transcribe(self, audio_path: Path) -> str:
        if self._model is None:
            self._model = gigaam.load_model(self._model_name)
        result = self._model.transcribe(str(audio_path))
        return str(result)
