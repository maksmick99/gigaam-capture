from __future__ import annotations

from pathlib import Path


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
            gigaam = self._import_gigaam()
            self._model = gigaam.load_model(self._model_name)
        result = self._model.transcribe(str(audio_path))
        return str(result)

    @staticmethod
    def _import_gigaam():
        try:
            import gigaam
        except ImportError as exc:  # pragma: no cover - depends on optional runtime
            raise RuntimeError(
                "The GigaAM runtime is not installed. Install it with "
                '"python -m pip install -e \\".[asr]\\"" or from the GigaAM source '
                "repository before running transcription."
            ) from exc
        return gigaam
