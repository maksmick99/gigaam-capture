from pathlib import Path

from gigaam_capture.config import build_app_paths, ensure_app_dirs
from gigaam_capture.history import HistoryStore
from gigaam_capture.models import TranscriptionRecord


def test_history_append_and_read(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    store = HistoryStore(paths)

    audio_path = paths.recordings_dir / "sample.wav"
    text_path = paths.recordings_dir / "sample.txt"
    audio_path.write_bytes(b"wav")

    record = TranscriptionRecord.create(
        audio_path=audio_path,
        text_path=text_path,
        model_name="v3_e2e_rnnt",
        duration_seconds=4.2,
        text="hello world",
        target_mode="clipboard",
    )
    store.append(record)

    recent = store.list_recent(limit=1)
    assert len(recent) == 1
    assert recent[0].text == "hello world"
    assert text_path.read_text(encoding="utf-8") == "hello world"
