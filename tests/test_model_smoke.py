from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.model


@pytest.mark.model
def test_real_model_load_and_transcribe(tmp_path: Path) -> None:
    """Load the default model and transcribe a short WAV without raising.

    This is a real-runtime smoke test and is intentionally excluded from the
    fast suite: it requires the GigaAM runtime and the downloaded
    ``v3_e2e_rnnt`` weights. Run it explicitly after installing the ``asr``
    extra:

        python -m pytest -m model -q tests/test_model_smoke.py

    Transcription quality is not an acceptance criterion here; the only thing
    asserted is that model loading and inference complete without an exception
    and return text.
    """
    gigaam = pytest.importorskip("gigaam", reason="GigaAM runtime is not installed")
    sf = pytest.importorskip("soundfile", reason="soundfile is not installed")
    np = pytest.importorskip("numpy", reason="numpy is not installed")

    samplerate = 16000
    duration_seconds = 0.5
    wav_path = tmp_path / "smoke.wav"
    time_axis = np.linspace(
        0, duration_seconds, int(samplerate * duration_seconds), endpoint=False
    )
    signal = (0.1 * np.sin(2 * np.pi * 440.0 * time_axis)).astype("float32")
    sf.write(wav_path, signal, samplerate)

    model = gigaam.load_model("v3_e2e_rnnt")
    try:
        result = model.transcribe(str(wav_path))
    finally:
        # The model may hold GPU/CPU resources; give it a best-effort release
        # so repeated smoke runs do not accumulate handles.
        release = getattr(model, "release", None)
        if callable(release):
            release()

    assert isinstance(str(result), str)
